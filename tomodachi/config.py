import ujson


def merge_dicts(dict1, dict2):
    context = dict(dict1)
    for k, v in dict2.items():
        if not context.get(k):
            context[k] = v
        elif isinstance(context.get(k), list) and isinstance(v, list):
            context[k] = context.get(k) + v
        elif isinstance(context.get(k), dict) and isinstance(v, dict):
            context[k] = merge_dicts(context.get(k), v)
        else:
            context[k] = v

    return context


def parse_config_files(config_files):
    if not config_files:
        return None
    if isinstance(config_files, str):
        config_files = [config_files]

    configuration = {}

    for config_file in config_files:
        with open(config_file) as f:
            data = f.read()
            json_data = ujson.loads(data)

            configuration = merge_dicts(configuration, json_data)

    return configuration
