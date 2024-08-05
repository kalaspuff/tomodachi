import asyncio
import inspect
import time
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, Awaitable, Dict, Literal, Optional, Union, cast, overload

import aiobotocore
import aiobotocore.client
import aiobotocore.config
import aiobotocore.session
import aiohttp
import aiohttp.client_exceptions
import botocore
import botocore.exceptions

from tomodachi.helpers.aws_credentials import Credentials, CredentialsMapping

if TYPE_CHECKING:
    from types_aiobotocore_sns import SNSClient
    from types_aiobotocore_sqs import SQSClient
else:
    SNSClient = aiobotocore.client.AioBaseClient
    SQSClient = aiobotocore.client.AioBaseClient


MAX_POOL_CONNECTIONS = 50
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 35
CLIENT_CREATION_TIME_LOCK = 45


class ClientConnector:
    __slots__ = (
        "clients",
        "_clients_context",
        "credentials",
        "client_creation_lock_time",
        "aliases",
        "locks",
        "conditions",
        "close_waiter",
    )

    clients: Dict[str, Optional[aiobotocore.client.AioBaseClient]]
    _clients_context: Dict[str, AsyncExitStack]
    credentials: Dict[str, Credentials]
    client_creation_lock_time: Dict[str, float]
    aliases: Dict[str, str]
    locks: Dict[str, asyncio.Lock]
    conditions: Dict[str, asyncio.Condition]
    close_waiter: Optional[asyncio.Future]

    def __init__(self) -> None:
        self.clients = {}
        self._clients_context = {}
        self.credentials = {}
        self.aliases = {}
        self.client_creation_lock_time = {}
        self.locks = {}
        self.conditions = {}
        self.close_waiter = None

    def setup_credentials(self, alias_name: str, credentials: CredentialsMapping) -> None:
        if not isinstance(credentials, Credentials):
            credentials = Credentials(credentials)
        self.credentials[alias_name] = credentials

    def get_client(self, alias_name: str) -> Optional[aiobotocore.client.AioBaseClient]:
        return self.clients.get(alias_name)

    def get_lock(self, alias_name: str) -> asyncio.Lock:
        if alias_name not in self.locks:
            self.locks[alias_name] = asyncio.Lock()
        return self.locks[alias_name]

    async def get_condition(self, alias_name: str) -> asyncio.Condition:
        if alias_name not in self.conditions:
            self.conditions[alias_name] = asyncio.Condition()
        return self.conditions[alias_name]

    @overload
    async def create_client(
        self,
        alias_name: Optional[str],
        credentials: Optional[CredentialsMapping],
        service_name: Literal["sns"],
    ) -> SNSClient: ...

    @overload
    async def create_client(
        self,
        alias_name: Optional[str],
        credentials: Optional[CredentialsMapping],
        service_name: Literal["sqs"],
    ) -> SQSClient: ...

    @overload
    async def create_client(
        self,
        alias_name: Optional[str] = None,
        credentials: Optional[CredentialsMapping] = None,
        service_name: Optional[str] = None,
    ) -> aiobotocore.client.AioBaseClient: ...

    async def create_client(
        self,
        alias_name: Optional[str] = None,
        credentials: Optional[CredentialsMapping] = None,
        service_name: Optional[str] = None,
    ) -> aiobotocore.client.AioBaseClient:
        if alias_name is None and service_name is None:
            raise Exception("Required 'alias_name' or 'service_name' is missing to create client")
        if service_name is None and alias_name is not None:
            service_name = alias_name
        if alias_name is None and service_name is not None:
            alias_name = service_name

        alias_name = str(alias_name)
        service_name = str(service_name)

        if alias_name in self.aliases and self.aliases[alias_name] != service_name:
            raise Exception(f"Client with alias '{alias_name}' has already been created for service '{service_name}'")

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

        if credentials is not None and not isinstance(credentials, Credentials):
            credentials = Credentials(credentials)

        async with self.get_lock(alias_name):
            client = self.get_client(alias_name)
            if client and self.client_creation_lock_time.get(alias_name, 0) + CLIENT_CREATION_TIME_LOCK > time.time():
                return client
            self.client_creation_lock_time[alias_name] = time.time() if client else 0

            if credentials is None:
                credentials = self.credentials[alias_name] if alias_name in self.credentials else Credentials()
            else:
                self.credentials[alias_name] = credentials
            if not credentials:
                credentials = Credentials()

            self.aliases[alias_name] = service_name

            session = aiobotocore.session.get_session()
            config = aiobotocore.config.AioConfig(
                connect_timeout=CONNECT_TIMEOUT, read_timeout=READ_TIMEOUT, max_pool_connections=MAX_POOL_CONNECTIONS
            )
            context_stack = AsyncExitStack()
            client_value = cast(
                Union[aiobotocore.client.AioBaseClient, Awaitable[aiobotocore.client.AioBaseClient]],
                context_stack.enter_async_context(
                    session.create_client(service_name, config=config, **credentials.dict())  # type: ignore[call-overload]
                ),
            )
            client_: aiobotocore.client.AioBaseClient = (
                (await client_value) if inspect.isawaitable(client_value) else client_value
            )

            old_client = self.get_client(alias_name)
            self.clients[alias_name] = client_
            self._clients_context[alias_name] = context_stack

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

            if alias_name in self.clients and self.clients[alias_name]:
                return cast(aiobotocore.client.AioBaseClient, self.clients[alias_name])

            return client_

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

        if not alias_name and client and client in self.clients.values():
            alias_name = [k for k, v in self.clients.items() if client == v][0]

        if not alias_name:
            return

        async with self.get_lock(alias_name):
            client = self.get_client(alias_name)
            context_stack = self._clients_context.get(alias_name)
            if not client or not context_stack:
                return

            try:
                if not fast:
                    await asyncio.sleep(0.25)
                task = client.close()
                if getattr(task, "_coro", None):
                    task = getattr(task, "_coro")
                await asyncio.wait(
                    [asyncio.ensure_future(task), asyncio.ensure_future(context_stack.aclose())], timeout=3
                )
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
        if not alias_name and client and client in self.clients.values():
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

    @overload
    def __overloaded_call__(
        self,
        alias_name: Optional[str],
        credentials: Optional[CredentialsMapping],
        service_name: Literal["sns"],
    ) -> AsyncIterator[SNSClient]: ...

    @overload
    def __overloaded_call__(
        self,
        alias_name: Optional[str] = None,
        credentials: Optional[CredentialsMapping] = None,
        *,
        service_name: Literal["sns"],
    ) -> AsyncIterator[SNSClient]: ...

    @overload
    def __overloaded_call__(
        self,
        alias_name: Optional[str],
        credentials: Optional[CredentialsMapping],
        service_name: Literal["sqs"],
    ) -> AsyncIterator[SQSClient]: ...

    @overload
    def __overloaded_call__(
        self,
        alias_name: Optional[str] = None,
        credentials: Optional[CredentialsMapping] = None,
        *,
        service_name: Literal["sqs"],
    ) -> AsyncIterator[SQSClient]: ...

    @overload
    def __overloaded_call__(
        self,
        alias_name: Optional[str] = None,
        credentials: Optional[CredentialsMapping] = None,
        service_name: Optional[str] = None,
    ) -> AsyncIterator[aiobotocore.client.AioBaseClient]: ...

    async def __overloaded_call__(
        self,
        alias_name: Optional[str] = None,
        credentials: Optional[CredentialsMapping] = None,
        service_name: Optional[str] = None,
    ) -> AsyncIterator[aiobotocore.client.AioBaseClient]:
        exc_iteration_count = 0
        while self.close_waiter and not self.close_waiter.done():
            try:
                await self.close_waiter
            except RuntimeError:
                exc_iteration_count += 1
                if exc_iteration_count >= 100:
                    raise
                await asyncio.sleep(0.1)

        client_name = alias_name or service_name or ""

        client = self.get_client(client_name)
        if not client:
            client = await self.create_client(alias_name, credentials, service_name)

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
            await self.reconnect_client(client_name, client=client)
            raise
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            if "The security token included in the request is invalid" in error_message:
                await self.close_client(client=client, fast=True)
            raise

    __call__ = asynccontextmanager(__overloaded_call__)


connector: ClientConnector = ClientConnector()
