from .core import get_race, list_races, get_season
from .config import set_bucket, set_manifest_path, get_config

__version__ = "0.0.9"


##  what is available to users
__all__ = ["get_race", "list_races", "get_season"]
