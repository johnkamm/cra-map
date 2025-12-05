"""
Map generation module for Michigan Cannabis License Map
Creates Folium interactive map with markers, clustering, and legend
"""

import pandas as pd
import folium
from folium.plugins import MarkerCluster
from collections import defaultdict
from typing import List, Dict
import logging

from .config import MAP, get_color, get_icon, is_active_status, get_opacity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MapGenerator:
    """Generate interactive Folium map with cannabis license locations"""

    def __init__(self):
        """Initialize map generator"""
        self.map = None
        self.marker_groups = {}

    def generate_map(self, df: pd.DataFrame, output_file: str = 'output/michigan_cannabis_map.html') -> folium.Map:
        """
        Generate complete map with all features.

        Args:
            df: DataFrame with geocoded license data
            output_file: Path to save HTML map

        Returns:
            Folium Map object
        """
        logger.info(f"Generating map with {len(df)} records...")

        # Filter to successfully geocoded records only
        df_geocoded = df[df['geocode_status'] == 'success'].copy()
        logger.info(f"Using {len(df_geocoded)} successfully geocoded records")

        # Initialize base map
        self._initialize_map()

        # Create feature groups for layer control
        self._create_feature_groups()

        # Aggregate markers by location
        location_data = self._aggregate_by_location(df_geocoded)
        logger.info(f"Aggregated into {len(location_data)} unique locations")

        # Add markers to map
        self._add_markers(location_data)

        # Add custom legend
        self._add_legend()

        # Add layer control
        folium.LayerControl(collapsed=False).add_to(self.map)

        # Save to file
        self._save_map(output_file)

        return self.map

    def _initialize_map(self):
        """Initialize base Folium map with multiple tile layers"""
        # Create map with no default tiles
        self.map = folium.Map(
            location=[MAP.CENTER_LAT, MAP.CENTER_LON],
            zoom_start=MAP.ZOOM_START,
            tiles=None
        )

        # Add base map tile layers
        folium.TileLayer(
            tiles='CartoDB positron',
            name='Street Map (Light)',
            control=True,
            overlay=False
        ).add_to(self.map)

        folium.TileLayer(
            tiles='OpenStreetMap',
            name='Street Map (OpenStreetMap)',
            control=True,
            overlay=False
        ).add_to(self.map)

        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite View',
            control=True,
            overlay=False
        ).add_to(self.map)

        logger.info("Initialized base map with multiple tile layers")

    def _create_feature_groups(self):
        """Create feature groups for layer control"""
        # Create groups for each license type
        categories = [
            ('Grower', 'AU'),
            ('Grower', 'MED'),
            ('Processor', 'AU'),
            ('Processor', 'MED'),
            ('Retailer', 'AU'),
            ('Retailer', 'MED'),
            ('Transporter', 'AU'),
            ('Transporter', 'MED')
        ]

        for category, market_type in categories:
            key = f"{category}_{market_type}"
            group_name = f"{category}s ({market_type})"

            # Create feature group with marker cluster
            fg = folium.FeatureGroup(name=group_name, show=True)
            marker_cluster = MarkerCluster(
                name=f'{group_name} Cluster',
                options={
                    'maxClusterRadius': MAP.MAX_CLUSTER_RADIUS,
                    'spiderfyOnMaxZoom': True,
                    'showCoverageOnHover': False,
                    'zoomToBoundsOnClick': True,
                    'disableClusteringAtZoom': MAP.DISABLE_CLUSTERING_AT_ZOOM
                }
            )
            marker_cluster.add_to(fg)

            self.marker_groups[key] = marker_cluster
            fg.add_to(self.map)

        # Create inactive licenses layer
        inactive_fg = folium.FeatureGroup(name="Inactive Licenses (All Types)", show=True)
        inactive_cluster = MarkerCluster(
            name='Inactive Licenses Cluster',
            options={
                'maxClusterRadius': MAP.MAX_CLUSTER_RADIUS,
                'spiderfyOnMaxZoom': True,
                'showCoverageOnHover': False,
                'zoomToBoundsOnClick': True,
                'disableClusteringAtZoom': MAP.DISABLE_CLUSTERING_AT_ZOOM
            }
        )
        inactive_cluster.add_to(inactive_fg)
        self.marker_groups['inactive'] = inactive_cluster
        inactive_fg.add_to(self.map)

        logger.info(f"Created {len(self.marker_groups)} feature groups with clustering")

    def _aggregate_by_location(self, df: pd.DataFrame) -> Dict:
        """
        Aggregate licenses by location (lat, lon).

        Args:
            df: Geocoded DataFrame

        Returns:
            Dictionary of locations with aggregated license data
        """
        location_data = defaultdict(list)

        for _, row in df.iterrows():
            # Round coordinates to detect duplicates
            lat = round(row['latitude'], MAP.PRECISION_DECIMAL_PLACES)
            lon = round(row['longitude'], MAP.PRECISION_DECIMAL_PLACES)
            key = (lat, lon)

            license_info = {
                'business_name': row['business_name'],
                'license_category': row['license_category'],
                'license_class': row.get('license_class'),
                'market_type': row['program_type'],
                'status': row['status'],
                'address': row['address'],
                'expiration_date': row['expiration_date'],
                'geocode_precision': row['geocode_precision']
            }

            location_data[key].append(license_info)

        return location_data

    def _add_markers(self, location_data: Dict):
        """
        Add markers to map for all locations.

        Args:
            location_data: Dictionary of aggregated location data
        """
        total_markers = 0

        for (lat, lon), licenses in location_data.items():
            # Determine primary license (first active, or first in list)
            primary = next((lic for lic in licenses if is_active_status(lic['status'])), licenses[0])

            # Create marker
            if len(licenses) == 1:
                # Single license at location
                self._create_single_marker(lat, lon, licenses[0])
            else:
                # Multiple licenses at location - use aggregated popup
                self._create_aggregated_marker(lat, lon, licenses, primary)

            total_markers += 1

        logger.info(f"Added {total_markers} markers to map")

    def _create_single_marker(self, lat: float, lon: float, license_info: Dict):
        """Create marker for single license"""
        category = license_info['license_category']
        market_type = license_info['market_type']
        status = license_info['status']
        is_active = is_active_status(status)

        # Get styling
        color = get_color(category, market_type, is_active)
        icon = get_icon(category, license_info['license_class'])
        opacity = get_opacity(is_active)

        # Create popup HTML
        popup_html = self._create_popup_html([license_info])

        # Create marker
        marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=license_info['business_name'],
            icon=folium.Icon(
                color=self._folium_color_map(color),
                icon=icon,
                prefix='fa'
            ),
            opacity=opacity
        )

        # Add to appropriate feature group (inactive or category-specific)
        if not is_active:
            marker.add_to(self.marker_groups['inactive'])
        else:
            group_key = f"{category}_{market_type}"
            if group_key in self.marker_groups:
                marker.add_to(self.marker_groups[group_key])

    def _create_aggregated_marker(self, lat: float, lon: float, licenses: List[Dict], primary: Dict):
        """Create marker for multiple licenses at same location"""
        category = primary['license_category']
        market_type = primary['market_type']
        status = primary['status']
        is_active = is_active_status(status)

        # Get styling from primary license
        color = get_color(category, market_type, is_active)
        icon = get_icon(category, primary['license_class'])
        opacity = get_opacity(is_active)

        # Create aggregated popup
        popup_html = self._create_popup_html(licenses, is_aggregated=True)

        # Create marker
        marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{len(licenses)} licenses at this location",
            icon=folium.Icon(
                color=self._folium_color_map(color),
                icon=icon,
                prefix='fa'
            ),
            opacity=opacity
        )

        # Add to appropriate feature group (inactive or category-specific)
        if not is_active:
            marker.add_to(self.marker_groups['inactive'])
        else:
            group_key = f"{category}_{market_type}"
            if group_key in self.marker_groups:
                marker.add_to(self.marker_groups[group_key])

    def _create_popup_html(self, licenses: List[Dict], is_aggregated: bool = False) -> str:
        """Create HTML content for popup"""
        from collections import defaultdict

        # Group licenses by type
        license_groups = defaultdict(list)
        for lic in licenses:
            # Create a key for grouping: market_type, category, and class
            license_class = lic['license_class']
            class_str = f" (Class {license_class})" if license_class and str(license_class) != 'nan' else ""
            group_key = (lic['market_type'], lic['license_category'], class_str, lic['status'])
            license_groups[group_key].append(lic)

        # Start HTML
        if is_aggregated:
            html = f"<div style='font-family: Arial, sans-serif;'>"
            html += f"<h4 style='margin: 5px 0;'>{len(licenses)} Licenses at this location</h4>"
        else:
            html = "<div style='font-family: Arial, sans-serif;'>"

        # Get business name and address from first license
        first_license = licenses[0]
        html += f"<b>{first_license['business_name']}</b><br>"
        html += f"{first_license['address']}<br>"

        # Show geocoding precision if city-level
        if first_license['geocode_precision'] == 'city':
            html += f"<small style='color: #FF9800;'>⚠ Approximate (city-level) location</small><br>"

        html += "<br>"

        # Show grouped license types with counts
        for (market_type, category, class_str, status), group_licenses in sorted(license_groups.items()):
            is_active = is_active_status(status)
            border_color = get_color(category, market_type, is_active)
            count = len(group_licenses)

            html += f"<div style='border-left: 3px solid {border_color}; padding-left: 8px; margin-bottom: 8px;'>"

            # License type with count
            if count > 1:
                html += f"<b>{market_type} - {category}{class_str}</b> ({count} licenses)<br>"
            else:
                html += f"<b>{market_type} - {category}{class_str}</b><br>"

            # Status with color coding
            status_color = '#4CAF50' if is_active else '#F44336'
            html += f"<span style='color: {status_color};'>Status: {status}</span><br>"

            # Show expiration dates (if multiple, show the range or all unique dates)
            expiration_dates = sorted(set([lic['expiration_date'] for lic in group_licenses]))
            if len(expiration_dates) == 1:
                html += f"Expires: {expiration_dates[0]}<br>"
            else:
                html += f"Expires: {', '.join(expiration_dates)}<br>"

            html += "</div>"

        html += "</div>"
        return html

    def _folium_color_map(self, hex_color: str) -> str:
        """
        Map hex color to Folium color name (Folium has limited colors).

        Args:
            hex_color: Hex color code

        Returns:
            Folium color name
        """
        # Map our hex colors to closest Folium colors
        color_mapping = {
            '#2D5016': 'darkgreen',  # Grower AU
            '#7CB342': 'green',      # Grower MED
            '#1565C0': 'darkblue',   # Processor AU
            '#42A5F5': 'blue',       # Processor MED
            '#6A1B9A': 'purple',     # Retailer AU
            '#AB47BC': 'pink',       # Retailer MED
            '#E65100': 'orange',     # Transporter AU
            '#FF9800': 'lightred',   # Transporter MED (closest to orange)
            '#BDBDBD': 'lightgray',  # Inactive
        }
        return color_mapping.get(hex_color, 'gray')

    def _add_legend(self):
        """Add custom HTML legend to map"""
        legend_html = '''
        <div style="position: fixed;
                    bottom: 30px; right: 10px; width: 250px;
                    background-color: white; border: 2px solid grey;
                    z-index: 9999; font-size: 13px; padding: 10px;
                    font-family: Arial, sans-serif;">
            <p style="margin: 0 0 8px 0;"><b>Michigan Cannabis Licenses</b></p>
            <p style="margin: 3px 0;"><i class="fa fa-leaf" style="color:#2D5016"></i> Grower (Adult Use)</p>
            <p style="margin: 3px 0;"><i class="fa fa-leaf" style="color:#7CB342"></i> Grower (Medical)</p>
            <p style="margin: 3px 0;"><i class="fa fa-flask" style="color:#1565C0"></i> Processor (Adult Use)</p>
            <p style="margin: 3px 0;"><i class="fa fa-flask" style="color:#42A5F5"></i> Processor (Medical)</p>
            <p style="margin: 3px 0;"><i class="fa fa-shopping-cart" style="color:#6A1B9A"></i> Retailer (Adult Use)</p>
            <p style="margin: 3px 0;"><i class="fa fa-shopping-cart" style="color:#AB47BC"></i> Retailer (Medical)</p>
            <p style="margin: 3px 0;"><i class="fa fa-truck" style="color:#E65100"></i> Transporter (Adult Use)</p>
            <p style="margin: 3px 0;"><i class="fa fa-truck" style="color:#FF9800"></i> Transporter (Medical)</p>
            <hr style="margin: 8px 0;">
            <p style="margin: 3px 0;"><i class="fa fa-circle" style="color:#BDBDBD"></i> Inactive/Closed</p>
            <p style="margin: 8px 0 0 0; font-size: 11px; color: #666;">
                Use layer control (top right) to filter license types
            </p>
        </div>
        '''
        self.map.get_root().html.add_child(folium.Element(legend_html))
        logger.info("Added custom legend")

    def _save_map(self, output_file: str):
        """Save map to HTML file"""
        from pathlib import Path
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.map.save(str(output_path))
        logger.info(f"Map saved to: {output_path}")
