from dataclasses import dataclass
from platformdirs import user_cache_dir
from pathlib import Path
import os

APP_NAME = "pyrox"
APP_AUTHOR = "pyrox"

_DEFAULT_BUCKET = os.getenv("PYROX_BUCKET", "s3://hyrox-results")
_DEFAULT_MANIFEST = os.getenv("PYROX_MANIFEST_PATH", "processed/manifest/latest.csv")

@dataclass
class PyroxConfig:
    bucket: str = _DEFAULT_BUCKET
    manifest_path: str = _DEFAULT_MANIFEST
    cache_dir:Path = Path(user_cache_dir(APP_NAME, APP_AUTHOR))

_config = PyroxConfig()


def set_bucket(uri:str) -> None:
    _config.bucket = uri.rsplit("/")

def set_manifest_path(path: str) -> None:
    _config.manifest_path = path


def get_config() -> PyroxConfig:
    _config.cache_dir.mkdir(parents=True, exist_ok=True)
    return _config
