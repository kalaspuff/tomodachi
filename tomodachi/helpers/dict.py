from typing import Any, Dict


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    if dict1 and not dict2:
        return dict(dict1)
    elif dict2 and not dict1:
        return dict(dict2)
    elif not dict1 and not dict2:
        return {}

    context = dict(dict1)
    for k, v2 in dict2.items():
        v1 = context.get(k)
        if not context.get(k):
            context[k] = v2
        elif isinstance(v1, list) and isinstance(v2, list):
            context[k] = v1 + v2
        elif isinstance(v1, dict) and isinstance(v2, dict):
            context[k] = merge_dicts(v1, v2)
        else:
            context[k] = v2

    return context


def get_item_by_path(dict: Dict, path: str, default: Any = None) -> Any:
    if "." not in path:
        raise KeyError("Key path must contain '.' ")
    doted_paths = path.split(".")
    item = dict.get(doted_paths[0], {})
    for i in range(1, len(doted_paths)):
        if i == len(doted_paths) - 1:
            default_value = default
        else:
            default_value = {}
        if isinstance(item, Dict):
            item = item.get(doted_paths[i], default_value)
        else:
            raise ValueError("Item at key path {} is not a Dict".format(".".join(doted_paths[:i])))
    return item
