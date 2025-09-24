from dataclasses import dataclass
from pathlib import Path
import os

from platformdirs import user_cache_dir

from pyrox.errors import ConfigError

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


def set_bucket(uri: str) -> None:
    """Configure the S3 bucket used for manifest/data lookups."""
    if not uri or not uri.strip():
        raise ConfigError("Bucket URI must be a non-empty string")

    cleaned = uri.strip().rstrip("/")
    _config.bucket = cleaned

def set_manifest_path(path: str) -> None:
    _config.manifest_path = path


def get_config() -> PyroxConfig:
    _config.cache_dir.mkdir(parents=True, exist_ok=True)
    return _config
