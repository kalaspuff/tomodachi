from typing import Dict


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
