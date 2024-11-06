from typing import Any

import yaml


def load_config(filename: str) -> Any:
    with open(filename, "r") as yaml_file:
        config = yaml.safe_load(yaml_file)
    return config