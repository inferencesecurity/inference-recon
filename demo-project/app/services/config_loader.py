# app/services/config_loader.py
import yaml


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)
