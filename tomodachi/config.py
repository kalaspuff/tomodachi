import ujson
from tomodachi.helpers.dict import merge_dicts
from typing import Dict, List, Optional


def parse_config_files(config_files: List[str]) -> Optional[Dict]:
    if not config_files:
        return None
    if isinstance(config_files, str):
        config_files = [config_files]

    configuration = {}  # type: Dict

    for config_file in config_files:
        with open(config_file) as f:
            data = f.read()
            json_data = ujson.loads(data)

            configuration = merge_dicts(configuration, json_data)

    return configuration
