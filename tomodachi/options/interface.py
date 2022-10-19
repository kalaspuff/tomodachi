from __future__ import annotations

from typing import Any, Dict, ItemsView, KeysView, Mapping, Optional, Tuple, Union

DEFAULT = object()


class OptionsInterface:
    _hierarchy: Tuple[str, ...] = ()
    _legacy_fallback: Dict[str, Union[str, Tuple[str, ...]]] = {}
    _parent: Optional[OptionsInterface] = None

    def get(self, item: str, default: Any = DEFAULT) -> Any:
        if "." in item:
            item, attr = item.split(".", 1)
            try:
                return getattr(self, item).get(attr)
            except AttributeError:
                if default is not DEFAULT:
                    return default
                raise

        if default is not DEFAULT:
            try:
                return getattr(self, item, default)
            except AttributeError:
                return default

        return getattr(self, item)

    def __getitem__(self, item: str) -> Any:
        return self.get(item)

    def __setattr__(self, item: str, value: Any) -> None:
        if not hasattr(self, item) and item not in self.keys():
            exc = AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")
            if hasattr(exc, "name"):
                setattr(exc, "name", item)
            if hasattr(exc, "obj"):
                setattr(exc, "obj", self)
            raise exc

        super().__setattr__(item, value)

    def __setitem__(self, item: str, value: Any) -> None:
        if "." in item:
            item, attr = item.split(".", 1)
            getattr(self, item)[attr] = value
            return

        if not hasattr(self, item):
            exc = AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")
            if hasattr(exc, "name"):
                setattr(exc, "name", item)
            if hasattr(exc, "obj"):
                setattr(exc, "obj", self)
            raise exc

        setattr(self, item, value)

    def keys(self) -> KeysView:
        return self.__annotations__.keys()

    def items(self) -> ItemsView:
        return self.asdict().items()

    def asdict(self, *, prefix: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key in self.keys():
            if key.startswith("_"):
                continue
            _prefix = f"{prefix}{str(key)}"
            value = getattr(self, key)
            if not isinstance(value, OptionsInterface):
                result[_prefix] = value
                continue
            values = value.asdict(prefix=f"{_prefix}.")
            for full_key, v in values.items():
                result[full_key] = v
        return result

    def __repr__(self) -> str:
        result: str = ""
        base_indent: int = 0 if not self._hierarchy else 2
        indent: int = 2
        prefix: str = ".".join(self._hierarchy)
        if prefix:
            cls_name = str(type(self)).split("'")[-2].split("tomodachi.options.definitions.", 1)[-1]
            result = f'∴ {self._hierarchy[-1]} <class: "{cls_name}" -- prefix: "{prefix}">:'
            prefix += "."
        prev: Tuple[str, ...] = self._hierarchy
        for full_key, value in self.asdict(prefix=prefix).items():
            key_prefix, key = full_key.rsplit(".", 1)
            curr: Tuple[str, ...] = tuple(key_prefix.split("."))
            if curr != prev:
                for i, subkey in enumerate(curr):
                    if i >= len(prev) or subkey != prev[i]:
                        indent = base_indent + ((i - len(self._hierarchy) + 1) * 2)
                        if result and not i:
                            result += "\n"
                        cls_name = (
                            str(type(self.get(".".join(curr[len(self._hierarchy) : i + 1]))))
                            .split("'")[-2]
                            .split("tomodachi.options.definitions.", 1)[-1]
                        )
                        lead_char = "·" if i != 0 else "∴"
                        result += f"\n{' ' * (indent - 2)}{lead_char} {subkey} <class: \"{cls_name}\" -- prefix: \"{'.'.join(curr)}\">:"
                        if i >= len(prev):
                            break
                prev = curr
            if type(value) is str:
                value = f'"{value}"'
            result += f"\n{' ' * indent}| {key} = {value}"
        return result.lstrip("\n") + "\n"

    def _load_initial_input(
        self, input_: Tuple[Tuple[str, Union[Mapping[str, Any], OptionsInterface], type], ...]
    ) -> None:
        for key, value, cls in input_:
            if not hasattr(value, "_default") and isinstance(value, cls):
                setattr(value, "_parent", self)
                setattr(self, key, value)
            else:
                setattr(self, key, cls(_parent=self))

        for key, value, cls in input_:
            if not hasattr(value, "_default") and not isinstance(value, cls):
                getattr(self, key)._load_keyword_options(**value)

    def _load_keyword_options(self, **kwargs: Any) -> None:
        if not self._parent:
            self._parent = kwargs.pop("_parent", None)

        flattened_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, (dict, OptionsInterface)):
                added_attributes = []
                error_attributes = []
                for subkey, subvalue in value.items():
                    key_str_tuple = self._legacy_fallback.get(f"{key}.{subkey}", f"{key}.{subkey}")
                    key_tuple = tuple((key_str_tuple,)) if not isinstance(key_str_tuple, tuple) else key_str_tuple
                    for full_key in key_tuple:
                        if full_key.startswith("."):
                            if not self._parent:
                                raise AttributeError(
                                    f"Cannot set attribute '{full_key}' on '{type(self).__name__}' object – deprecated attribute has moved and OptionsInterface has no parent"
                                )
                            self._parent[full_key[1:]] = subvalue
                            continue
                        try:
                            self.get(full_key)
                            flattened_kwargs[full_key] = subvalue
                            added_attributes.append(subkey)
                        except AttributeError:
                            if isinstance(value, OptionsInterface):
                                raise
                            if isinstance(value, dict):
                                error_attributes.append(subkey)
                if error_attributes and added_attributes:
                    raise AttributeError(f"Invalid attribute(s) in dict: {', '.join(error_attributes)}")
                elif error_attributes and not added_attributes:
                    key_str_tuple = self._legacy_fallback.get(key, key)
                    key_tuple = tuple((key_str_tuple,)) if not isinstance(key_str_tuple, tuple) else key_str_tuple
                    for full_key in key_tuple:
                        if full_key.startswith("."):
                            if not self._parent:
                                raise AttributeError(
                                    f"Cannot set attribute '{full_key}' on '{type(self).__name__}' object – deprecated attribute has moved and OptionsInterface has no parent"
                                )
                            self._parent[full_key[1:]] = value
                            continue
                        flattened_kwargs[full_key] = value
            else:
                key_str_tuple = self._legacy_fallback.get(key, key)
                key_tuple = tuple((key_str_tuple,)) if not isinstance(key_str_tuple, tuple) else key_str_tuple
                for full_key in key_tuple:
                    if full_key.startswith("."):
                        if not self._parent:
                            raise AttributeError(
                                f"Cannot set attribute '{full_key}' on '{type(self).__name__}' object – deprecated attribute has moved and OptionsInterface has no parent"
                            )
                        self._parent[full_key[1:]] = value
                        continue
                    flattened_kwargs[full_key] = value

        for key, value in flattened_kwargs.items():
            self.__setitem__(key, value)
