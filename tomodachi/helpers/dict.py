from typing import Dict


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
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
