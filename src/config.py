"""
Configuration file for Michigan Cannabis License Map
Contains color schemes, icon mappings, and service settings
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class ColorScheme:
    """Color definitions for license types (Hex colors for Folium)"""
    GROWER_AU: str = '#2D5016'
    GROWER_MED: str = '#7CB342'
    PROCESSOR_AU: str = '#1565C0'
    PROCESSOR_MED: str = '#42A5F5'
    RETAILER_AU: str = '#6A1B9A'
    RETAILER_MED: str = '#AB47BC'
    TRANSPORTER_AU: str = '#E65100'
    TRANSPORTER_MED: str = '#FF9800'
    INACTIVE: str = '#BDBDBD'
    LATE_RENEWAL: str = '#FF9800'


@dataclass
class IconMapping:
    """FontAwesome icon mappings for license types"""
    GROWER_A: str = 'leaf'
    GROWER_B: str = 'leaf'
    GROWER_C: str = 'leaf'
    GROWER_EXCESS: str = 'leaf'
    GROWER_MICROBUSINESS: str = 'seedling'
    PROCESSOR: str = 'flask'
    RETAILER: str = 'shopping-cart'
    TRANSPORTER: str = 'truck'


@dataclass
class GeocodingConfig:
    """Geocoding service configuration"""
    USER_AGENT: str = 'michigan_cannabis_map_v1'
    RATE_LIMIT: float = 1.0  # seconds between requests
    TIMEOUT: int = 10
    CACHE_FILE: str = 'data/cache/geocode_cache.json'
    CHECKPOINT_INTERVAL: int = 100  # Save cache every N records


@dataclass
class MapConfig:
    """Folium map configuration"""
    CENTER_LAT: float = 44.3148  # Michigan center
    CENTER_LON: float = -85.6024
    ZOOM_START: int = 7
    TILES: str = 'OpenStreetMap'
    MAX_CLUSTER_RADIUS: int = 50
    DISABLE_CLUSTERING_AT_ZOOM: int = 15
    PRECISION_DECIMAL_PLACES: int = 6  # For duplicate detection


# Michigan coordinate bounds for validation
MI_LAT_MIN = 41.0
MI_LAT_MAX = 48.0
MI_LON_MIN = -90.0
MI_LON_MAX = -82.0

# Export config instances
COLORS = ColorScheme()
ICONS = IconMapping()
GEOCODING = GeocodingConfig()
MAP = MapConfig()


def get_color(business_category: str, market_type: str, is_active: bool) -> str:
    """
    Get the appropriate color for a license based on category, market type, and status.

    Args:
        business_category: "Grower", "Processor", "Retailer", or "Transporter"
        market_type: "AU" (Adult Use) or "MED" (Medical)
        is_active: True if license is active, False otherwise

    Returns:
        Hex color string
    """
    if not is_active:
        return COLORS.INACTIVE

    key = f"{business_category.upper()}_{market_type.upper()}"
    color_map = {
        'GROWER_AU': COLORS.GROWER_AU,
        'GROWER_MED': COLORS.GROWER_MED,
        'PROCESSOR_AU': COLORS.PROCESSOR_AU,
        'PROCESSOR_MED': COLORS.PROCESSOR_MED,
        'RETAILER_AU': COLORS.RETAILER_AU,
        'RETAILER_MED': COLORS.RETAILER_MED,
        'TRANSPORTER_AU': COLORS.TRANSPORTER_AU,
        'TRANSPORTER_MED': COLORS.TRANSPORTER_MED,
    }

    return color_map.get(key, COLORS.INACTIVE)


def get_icon(business_category: str, license_class: str = None) -> str:
    """
    Get the appropriate FontAwesome icon for a license.

    Args:
        business_category: "Grower", "Processor", "Retailer", or "Transporter"
        license_class: For growers: "A", "B", "C", "Excess", "Microbusiness"

    Returns:
        FontAwesome icon name
    """
    if business_category == 'Grower':
        if license_class == 'Microbusiness':
            return ICONS.GROWER_MICROBUSINESS
        elif license_class in ['A', 'B', 'C', 'Excess']:
            return ICONS.GROWER_A  # All use leaf icon (same base)
        else:
            return ICONS.GROWER_A
    elif business_category == 'Processor':
        return ICONS.PROCESSOR
    elif business_category == 'Retailer':
        return ICONS.RETAILER
    elif business_category == 'Transporter':
        return ICONS.TRANSPORTER
    else:
        return 'circle'  # Default fallback


def is_active_status(status: str) -> bool:
    """
    Determine if a license status is considered active.

    Args:
        status: Status string from CSV

    Returns:
        True if active, False otherwise
    """
    status_lower = status.lower()
    return 'active' in status_lower and 'late' not in status_lower


def get_opacity(is_active: bool) -> float:
    """Get marker opacity based on status"""
    return 1.0 if is_active else 0.6
