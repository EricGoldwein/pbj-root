"""Isolated synthetic demo providers. Never loaded into CMS/PBJ production tables."""

from demo_data.sunny_pastures import (
    SUNNY_PASTURES_ID,
    SUNNY_PASTURES_LOCAL_PATH,
    SUNNY_PASTURES_PATH,
    is_demo_provider_id,
    load_sunny_pastures_provider,
)

__all__ = (
    'SUNNY_PASTURES_ID',
    'SUNNY_PASTURES_LOCAL_PATH',
    'SUNNY_PASTURES_PATH',
    'is_demo_provider_id',
    'load_sunny_pastures_provider',
)
