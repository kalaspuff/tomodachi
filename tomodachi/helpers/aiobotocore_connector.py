import asyncio
import inspect
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Dict, Optional, cast

import aiobotocore
import aiobotocore.client
import aiobotocore.config
import aiohttp
import aiohttp.client_exceptions
import botocore
import botocore.exceptions

MAX_POOL_CONNECTIONS = 50
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 35
CLIENT_CREATION_TIME_LOCK = 45


class ClientConnector(object):
    __slots__ = (
        "clients",
        "credentials",
        "client_creation_lock_time",
        "aliases",
        "locks",
        "close_waiter",
    )

    clients: Dict[str, Optional[aiobotocore.client.AioBaseClient]]
    credentials: Dict[str, Dict]
    client_creation_lock_time: Dict[str, float]
    aliases: Dict[str, str]
    locks: Dict[str, asyncio.Lock]
    close_waiter: Optional[asyncio.Future]

    def __init__(self) -> None:
        self.clients = {}
        self.credentials = {}
        self.aliases = {}
        self.client_creation_lock_time = {}
        self.locks = {}
        self.close_waiter = None

    def setup_credentials(self, alias_name: str, credentials: Dict) -> None:
        self.credentials[alias_name] = credentials

    def get_client(self, alias_name: str) -> Optional[aiobotocore.client.AioBaseClient]:
        return self.clients.get(alias_name)

    def get_lock(self, alias_name: str) -> asyncio.Lock:
        if alias_name not in self.locks:
            self.locks[alias_name] = asyncio.Lock()
        return self.locks[alias_name]

    async def create_client(
        self, alias_name: Optional[str] = None, credentials: Optional[Dict] = None, service_name: Optional[str] = None
    ) -> aiobotocore.client.AioBaseClient:
        if service_name is None and alias_name is not None:
            service_name = alias_name
        if alias_name is None and service_name is not None:
            alias_name = service_name

        alias_name = str(alias_name)
        service_name = str(service_name)

        exc_iteration_count = 0
        while self.close_waiter:
            if self.close_waiter.done():
                self.close_waiter = None
            else:
                try:
                    await self.close_waiter
                except RuntimeError:
                    exc_iteration_count += 1
                    if exc_iteration_count >= 100:
                        raise
                    await asyncio.sleep(0.1)

        async with self.get_lock(alias_name):
            client = self.get_client(alias_name)
            if self.client_creation_lock_time.get(alias_name, 0) + CLIENT_CREATION_TIME_LOCK > time.time():
                if client:
                    return client
            self.client_creation_lock_time[alias_name] = time.time() if client else 0

            if not credentials:
                credentials = self.credentials.get(alias_name, {})
            else:
                self.credentials[alias_name] = credentials
            if not credentials:
                credentials = {}

            self.aliases[alias_name] = service_name

            session = aiobotocore.get_session()
            config = aiobotocore.config.AioConfig(
                connect_timeout=CONNECT_TIMEOUT, read_timeout=READ_TIMEOUT, max_pool_connections=MAX_POOL_CONNECTIONS
            )

            create_client_func = session._create_client if hasattr(session, "_create_client") else session.create_client
            client_value = create_client_func(service_name, config=config, **credentials)
            if inspect.isawaitable(client_value):
                client = await cast(Awaitable, client_value)
            else:
                client = client_value

            old_client = self.get_client(alias_name)
            self.clients[alias_name] = cast(aiobotocore.client.AioBaseClient, client)

            if old_client:
                try:
                    await asyncio.sleep(1)
                    task = old_client.close()
                    if getattr(task, "_coro", None):
                        task = getattr(task, "_coro")
                    await asyncio.wait([asyncio.ensure_future(task)], timeout=3)
                    await asyncio.sleep(0.25)  # SSL termination sleep
                except (Exception, RuntimeError, asyncio.CancelledError, BaseException):
                    pass

            return cast(aiobotocore.client.AioBaseClient, self.clients.get(alias_name) or client)

    async def close_client(
        self,
        alias_name: Optional[str] = None,
        client: Optional[aiobotocore.client.AioBaseClient] = None,
        fast: bool = False,
    ) -> None:
        exc_iteration_count = 0
        while self.close_waiter:
            if self.close_waiter.done():
                self.close_waiter = None
            else:
                try:
                    await self.close_waiter
                except RuntimeError:
                    exc_iteration_count += 1
                    if exc_iteration_count >= 100:
                        raise
                    await asyncio.sleep(0.1)

        if not alias_name and client:
            if client in self.clients.values():
                alias_name = [k for k, v in self.clients.items() if client == v][0]

        if not alias_name:
            return

        async with self.get_lock(alias_name):
            client = self.get_client(alias_name)
            if not client:
                return

            try:
                if not fast:
                    await asyncio.sleep(0.25)
                task = client.close()
                if getattr(task, "_coro", None):
                    task = getattr(task, "_coro")
                await asyncio.wait([asyncio.ensure_future(task)], timeout=3)
                if not fast:
                    await asyncio.sleep(0.25)  # SSL termination sleep
                else:
                    await asyncio.sleep(0)
            except (Exception, RuntimeError, asyncio.CancelledError, BaseException):
                pass

            self.clients[alias_name] = None

    async def reconnect_client(
        self, alias_name: Optional[str] = None, client: Optional[aiobotocore.client.AioBaseClient] = None
    ) -> aiobotocore.client.AioBaseClient:
        if not alias_name and client:
            if client in self.clients.values():
                alias_name = [k for k, v in self.clients.items() if client == v][0]

        service_name = self.aliases.get(alias_name or "")
        if not service_name:
            raise Exception("Client has never been created in the first place")

        return await self.create_client(alias_name, service_name=service_name)

    async def close(self, fast: bool = False) -> None:
        if self.close_waiter and not self.close_waiter.done():
            return

        clients = self.clients

        self.clients = {}
        self.credentials = {}
        self.aliases = {}
        self.client_creation_lock_time = {}
        self.locks = {}

        if not clients:
            return

        self.close_waiter = asyncio.Future()
        if not fast:
            await asyncio.sleep(0.25)

        tasks = []
        for _, client in clients.items():
            if not client:
                continue
            try:
                task = client.close()
                if getattr(task, "_coro", None):
                    task = getattr(task, "_coro")
                tasks.append(asyncio.ensure_future(task))
            except (Exception, RuntimeError, asyncio.CancelledError, BaseException):
                pass

        try:
            await asyncio.wait(tasks, timeout=3)
            if not fast:
                await asyncio.sleep(0.25)  # SSL termination sleep
            else:
                await asyncio.sleep(0)
        except (Exception, RuntimeError, asyncio.CancelledError, BaseException):
            pass

        if self.close_waiter:
            self.close_waiter.set_result(None)

    @asynccontextmanager
    async def __call__(
        self, alias_name: Optional[str] = None, credentials: Optional[Dict] = None, service_name: Optional[str] = None
    ) -> AsyncIterator[Any]:
        exc_iteration_count = 0
        while self.close_waiter and not self.close_waiter.done():
            try:
                await self.close_waiter
            except RuntimeError:
                exc_iteration_count += 1
                if exc_iteration_count >= 100:
                    raise
                await asyncio.sleep(0.1)

        if not self.get_client(alias_name or service_name or ""):
            await self.create_client(alias_name, credentials, service_name)
        client = self.get_client(alias_name or service_name or "")

        try:
            yield client
        except (
            botocore.exceptions.NoRegionError,
            botocore.exceptions.PartialCredentialsError,
            botocore.exceptions.NoCredentialsError,
        ):
            await self.close_client(client=client, fast=True)
            raise
        except (aiohttp.client_exceptions.ServerDisconnectedError, asyncio.TimeoutError, RuntimeError):
            await self.reconnect_client(client=client)
            raise
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            if "The security token included in the request is invalid" in error_message:
                await self.close_client(client=client, fast=True)
            raise


connector: ClientConnector = ClientConnector()
