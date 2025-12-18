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
        self.marker_groups = {}  # MarkerCluster objects for adding markers
        self.feature_groups = {}  # FeatureGroup objects for layer control

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

        # Load and add For Sale properties
        self._load_and_add_forsale_properties()

        # Aggregate markers by location
        location_data = self._aggregate_by_location(df_geocoded)
        logger.info(f"Aggregated into {len(location_data)} unique locations")

        # Add markers to map
        self._add_markers(location_data)

        # Add custom legend (removed - now using Filter Licenses panel as legend)
        # self._add_legend()

        # Add search control
        self._add_search_control(location_data)

        # Add custom layer control with dependent filtering
        self._add_custom_layer_control()

        # Add base layer control (for map tiles only)
        folium.LayerControl(collapsed=False).add_to(self.map)

        # Add footer
        self._add_footer()

        # Add favicon
        self._add_favicon()

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

        # Add satellite view first
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite View',
            control=True,
            overlay=False
        ).add_to(self.map)

        # Add OpenStreetMap second (will be selected by default as the last base layer)
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='OpenStreetMap',
            control=True,
            overlay=False
        ).add_to(self.map)

        logger.info("Initialized base map with OpenStreetMap default and Satellite view")

    def _create_feature_groups(self):
        """Create feature groups for layer control"""
        # Create groups for each license type and status combination
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

        # Create Active groups first (will appear at top alphabetically)
        for category, market_type in categories:
            key_active = f"{category}_{market_type}_active"
            group_name_active = f"Active - {category}s ({market_type})"

            # Create active feature group with marker cluster
            fg_active = folium.FeatureGroup(name=group_name_active, show=True)
            marker_cluster_active = MarkerCluster(
                name=f'{group_name_active} Cluster',
                options={
                    'maxClusterRadius': MAP.MAX_CLUSTER_RADIUS,
                    'spiderfyOnMaxZoom': True,
                    'showCoverageOnHover': False,
                    'zoomToBoundsOnClick': True,
                    'disableClusteringAtZoom': MAP.DISABLE_CLUSTERING_AT_ZOOM
                }
            )
            marker_cluster_active.add_to(fg_active)
            self.marker_groups[key_active] = marker_cluster_active  # For adding markers
            self.feature_groups[group_name_active] = fg_active  # For layer control
            fg_active.add_to(self.map)

        # Create Inactive groups
        for category, market_type in categories:
            key_inactive = f"{category}_{market_type}_inactive"
            group_name_inactive = f"Inactive - {category}s ({market_type})"

            # Create inactive feature group with marker cluster
            fg_inactive = folium.FeatureGroup(name=group_name_inactive, show=True)
            marker_cluster_inactive = MarkerCluster(
                name=f'{group_name_inactive} Cluster',
                options={
                    'maxClusterRadius': MAP.MAX_CLUSTER_RADIUS,
                    'spiderfyOnMaxZoom': True,
                    'showCoverageOnHover': False,
                    'zoomToBoundsOnClick': True,
                    'disableClusteringAtZoom': MAP.DISABLE_CLUSTERING_AT_ZOOM
                }
            )
            marker_cluster_inactive.add_to(fg_inactive)
            self.marker_groups[key_inactive] = marker_cluster_inactive  # For adding markers
            self.feature_groups[group_name_inactive] = fg_inactive  # For layer control
            fg_inactive.add_to(self.map)

        # Create For Sale feature group
        fg_forsale = folium.FeatureGroup(name='Retail - For Sale', show=True)
        self.marker_groups['forsale'] = fg_forsale  # No clustering for For Sale
        self.feature_groups['Retail - For Sale'] = fg_forsale
        fg_forsale.add_to(self.map)

        logger.info(f"Created {len(self.marker_groups)} feature groups with clustering")

    def _load_and_add_forsale_properties(self):
        """Load and add For Sale property markers to map"""
        from pathlib import Path

        forsale_file = Path('data/processed/forsale_properties.csv')
        if not forsale_file.exists():
            logger.warning("For Sale properties file not found, skipping")
            return

        # Load For Sale properties
        df_forsale = pd.read_csv(forsale_file)
        df_forsale = df_forsale[df_forsale['geocode_status'] == 'success']

        logger.info(f"Adding {len(df_forsale)} For Sale properties to map")

        # Add marker for each For Sale property
        for _, row in df_forsale.iterrows():
            # Check if sq_ft is available (not None, not NaN, not empty string)
            has_sq_ft = row['sq_ft'] and pd.notna(row['sq_ft']) and str(row['sq_ft']).strip() != ''

            # Build size line conditionally
            size_line = f"<b>Size:</b> {row['sq_ft']} sq ft<br>" if has_sq_ft else ""

            # Create popup HTML with listing link (bright fluorescent green)
            popup_html = f'''
            <div style='font-family: Arial, sans-serif;'>
                <h4 style='margin: 5px 0; color: #39FF14; text-shadow: 0 0 2px #39FF14;'>For Sale</h4>
                <b>{row['address']}</b><br>
                <div style='margin-top: 5px; font-size: 13px;'>
                    <b>Price:</b> {row['price']}<br>
                    {size_line}
                </div>
                <br>
                <a href="{row['url']}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: bold;">View Listing</a>
            </div>
            '''

            # Create marker with bright fluorescent green dollar sign icon
            # Using DivIcon for custom bright green color
            icon_html = f'''
            <div style="
                background-color: #39FF14;
                border: 2px solid #000;
                border-radius: 50%;
                width: 35px;
                height: 35px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 0 10px #39FF14, 0 3px 10px rgba(0,0,0,0.5);
            ">
                <i class="fa fa-dollar-sign" style="color: #000; font-size: 18px; font-weight: bold;"></i>
            </div>
            '''

            marker = folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"For Sale: {row['address']}",
                icon=folium.DivIcon(html=icon_html)
            )

            # Add to For Sale feature group
            marker.add_to(self.marker_groups['forsale'])

        logger.info(f"Added {len(df_forsale)} For Sale markers")

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
            # Group licenses by (category, market_type) to create separate markers for each type
            from collections import defaultdict
            grouped = defaultdict(list)
            for lic in licenses:
                key = (lic['license_category'], lic['market_type'])
                grouped[key].append(lic)

            # If multiple license types at same location, offset them slightly
            num_groups = len(grouped)
            offset_multiplier = 0.00008  # ~9 meters offset

            for idx, ((category, market_type), group_licenses) in enumerate(grouped.items()):
                # Calculate offset for this marker
                if num_groups > 1:
                    # Offset in a circle pattern around the original point
                    import math
                    angle = (2 * math.pi * idx) / num_groups
                    lat_offset = offset_multiplier * math.cos(angle)
                    lon_offset = offset_multiplier * math.sin(angle)
                    marker_lat = lat + lat_offset
                    marker_lon = lon + lon_offset
                else:
                    marker_lat = lat
                    marker_lon = lon

                # Create marker for this license type
                if len(group_licenses) == 1:
                    self._create_single_marker(marker_lat, marker_lon, group_licenses[0])
                else:
                    # Multiple licenses of same type at location
                    primary = next((lic for lic in group_licenses if is_active_status(lic['status'])), group_licenses[0])
                    self._create_aggregated_marker(marker_lat, marker_lon, group_licenses, primary)

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
        popup_html = self._create_popup_html([license_info], lat=lat, lon=lon)

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

        # Add to appropriate feature group based on active/inactive status
        status_suffix = 'active' if is_active else 'inactive'
        group_key = f"{category}_{market_type}_{status_suffix}"
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
        popup_html = self._create_popup_html(licenses, lat=lat, lon=lon, is_aggregated=True)

        # Create tooltip with unique business names
        unique_businesses = list(set([
            str(lic['business_name']) for lic in licenses
            if lic['business_name'] and pd.notna(lic['business_name'])
        ]))
        if len(unique_businesses) == 1:
            tooltip_text = unique_businesses[0]
        elif len(unique_businesses) <= 3:
            tooltip_text = ", ".join(unique_businesses)
        elif len(unique_businesses) > 0:
            tooltip_text = f"{unique_businesses[0]} + {len(unique_businesses) - 1} more"
        else:
            tooltip_text = f"{len(licenses)} licenses at this location"

        # Create marker
        marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=tooltip_text,
            icon=folium.Icon(
                color=self._folium_color_map(color),
                icon=icon,
                prefix='fa'
            ),
            opacity=opacity
        )

        # Add to appropriate feature group based on active/inactive status
        status_suffix = 'active' if is_active else 'inactive'
        group_key = f"{category}_{market_type}_{status_suffix}"
        if group_key in self.marker_groups:
            marker.add_to(self.marker_groups[group_key])

    def _create_popup_html(self, licenses: List[Dict], lat: float = None, lon: float = None, is_aggregated: bool = False) -> str:
        """Create HTML content for popup"""
        from collections import defaultdict

        # Count active vs inactive licenses
        active_count = sum(1 for lic in licenses if is_active_status(lic['status']))
        inactive_count = len(licenses) - active_count

        # Group licenses by type
        license_groups = defaultdict(list)
        for lic in licenses:
            # Create a key for grouping: market_type, category, and class
            license_class = lic['license_class']
            class_str = f" (Class {license_class})" if license_class and str(license_class) != 'nan' else ""
            is_active = is_active_status(lic['status'])
            group_key = (is_active, lic['market_type'], lic['license_category'], class_str, lic['status'])
            license_groups[group_key].append(lic)

        # Start HTML with active/inactive breakdown
        html = f"<div style='font-family: Arial, sans-serif;'>"
        if is_aggregated:
            if inactive_count > 0:
                html += f"<h4 style='margin: 5px 0;'>{active_count} Active License{'s' if active_count != 1 else ''} ({inactive_count} Inactive) at this location</h4>"
            else:
                html += f"<h4 style='margin: 5px 0;'>{active_count} Active License{'s' if active_count != 1 else ''} at this location</h4>"

        # Get business name and address from first license
        first_license = licenses[0]
        html += f"<b>{first_license['business_name']}</b><br>"
        html += f"{first_license['address']}<br>"

        # Show geocoding precision if city-level
        if first_license['geocode_precision'] == 'city':
            html += f"<small style='color: #FF9800;'>⚠ Approximate (city-level) location</small><br>"

        html += "<br>"

        # Show grouped license types with counts, sorted with active licenses first
        for (is_active, market_type, category, class_str, status), group_licenses in sorted(license_groups.items(), key=lambda x: (not x[0][0], x[0][1], x[0][2], x[0][3])):
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

        # Add Google Maps directions link
        if lat is not None and lon is not None:
            directions_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
            html += f"<br><a href='{directions_url}' target='_blank' style='color: #0066cc; text-decoration: none; font-weight: bold;'><i class='fa fa-map-marker-alt'></i> Get Directions</a>"

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
                Use Filter Licenses panel (top right) to toggle Active/Inactive status and license types
            </p>
        </div>
        '''
        self.map.get_root().html.add_child(folium.Element(legend_html))
        logger.info("Added custom legend")

    def _add_search_control(self, location_data: Dict):
        """Add search control for finding locations by company name, city, or zip code"""
        import json
        import re

        # Build search index with unique locations
        search_index = []
        for (lat, lon), licenses in location_data.items():
            # Get unique company names at this location (filter out None/NaN values)
            company_names = list(set([
                str(lic['business_name']) for lic in licenses
                if lic['business_name'] and pd.notna(lic['business_name'])
            ]))

            # Extract city and zip from address (assuming format: "address, city state zip")
            address = licenses[0]['address']
            city = ""
            zip_code = ""

            # Try to extract city and zip from address
            address_parts = address.split(',')
            if len(address_parts) >= 2:
                # Last part usually contains "City ST Zip"
                last_part = address_parts[-1].strip()
                # Extract zip code (5 digits)
                zip_match = re.search(r'\b\d{5}\b', last_part)
                if zip_match:
                    zip_code = zip_match.group()
                # Extract city (everything before state abbreviation)
                city_match = re.search(r'^(.+?)\s+[A-Z]{2}\s+\d{5}', last_part)
                if city_match:
                    city = city_match.group(1).strip()
                else:
                    # If no state/zip pattern, just take the text before zip
                    city = last_part.replace(zip_code, '').strip()

            search_index.append({
                'companies': company_names,
                'city': city,
                'zip': zip_code,
                'address': address,
                'lat': lat,
                'lon': lon,
                'count': len(licenses)
            })

        # Convert to JSON for JavaScript
        search_data_json = json.dumps(search_index)

        search_html = f'''
        <div id="search-control" style="position: fixed;
                    top: 10px; left: 60px;
                    background-color: white; border: 2px solid rgba(0,0,0,0.2);
                    border-radius: 4px;
                    z-index: 1000; padding: 10px;
                    font-family: Arial, sans-serif;
                    box-shadow: 0 1px 5px rgba(0,0,0,0.4);">
            <div style="display: flex; align-items: center; gap: 5px;">
                <input type="text" id="search-input" placeholder="Search by company, city, or zip..."
                    style="width: 250px; padding: 6px; border: 1px solid #ccc; border-radius: 3px; font-size: 13px;">
                <button id="search-button" style="padding: 6px 12px; background-color: #4CAF50; color: white;
                    border: none; border-radius: 3px; cursor: pointer; font-size: 13px;">Search</button>
                <button id="clear-search" style="padding: 6px 12px; background-color: #f44336; color: white;
                    border: none; border-radius: 3px; cursor: pointer; font-size: 13px;">Clear</button>
            </div>
            <div id="search-results" style="margin-top: 8px; font-size: 12px; color: #666; max-height: 200px; overflow-y: auto;"></div>
        </div>

        <script>
        (function() {{
            var searchData = {search_data_json};
            console.log('Search data loaded:', searchData.length, 'locations');

            function performSearch() {{
                var query = document.getElementById('search-input').value.toLowerCase().trim();
                var resultsDiv = document.getElementById('search-results');

                console.log('Search query:', query);

                if (!query) {{
                    resultsDiv.innerHTML = '<span style="color: #f44336;">Please enter a search term</span>';
                    return;
                }}

                // Clear previous highlight when starting new search
                if (window.currentHighlight) {{
                    var mapKeys = Object.keys(window).filter(function(key) {{
                        return key.startsWith('map_') && window[key] && window[key].removeLayer;
                    }});
                    if (mapKeys.length > 0) {{
                        var mapObj = window[mapKeys[0]];
                        mapObj.removeLayer(window.currentHighlight);
                        window.currentHighlight = null;
                    }}
                }}
                if (window.highlightTimeout) {{
                    clearTimeout(window.highlightTimeout);
                    window.highlightTimeout = null;
                }}

                // Search through the data with scoring for better ranking
                var matches = [];
                searchData.forEach(function(location) {{
                    var matchFound = false;
                    var matchType = '';
                    var matchScore = 0; // Higher score = better match
                    var matchedCompany = location.companies[0]; // Default to first company

                    // Search company names with scoring
                    for (var j = 0; j < location.companies.length; j++) {{
                        var company = location.companies[j];
                        if (company && typeof company === 'string') {{
                            var companyLower = company.toLowerCase();
                            if (companyLower === query) {{
                                // Exact match - highest priority
                                matchFound = true;
                                matchType = 'Company';
                                matchScore = Math.max(matchScore, 1000);
                                matchedCompany = company; // Store the matching company
                            }} else if (companyLower.startsWith(query)) {{
                                // Starts with - high priority
                                matchFound = true;
                                matchType = 'Company';
                                matchScore = Math.max(matchScore, 500);
                                matchedCompany = company; // Store the matching company
                            }} else if (companyLower.includes(query)) {{
                                // Contains - medium priority
                                matchFound = true;
                                matchType = 'Company';
                                matchScore = Math.max(matchScore, 100);
                                matchedCompany = company; // Store the matching company
                            }}
                        }}
                    }}

                    // Search city
                    if (location.city && typeof location.city === 'string') {{
                        var cityLower = location.city.toLowerCase();
                        if (cityLower === query) {{
                            matchFound = true;
                            matchType = 'City';
                            matchScore = Math.max(matchScore, 900);
                        }} else if (cityLower.startsWith(query)) {{
                            matchFound = true;
                            matchType = 'City';
                            matchScore = Math.max(matchScore, 400);
                        }} else if (cityLower.includes(query)) {{
                            matchFound = true;
                            matchType = 'City';
                            matchScore = Math.max(matchScore, 50);
                        }}
                    }}

                    // Search zip - exact or starts with
                    if (location.zip && typeof location.zip === 'string') {{
                        if (location.zip === query) {{
                            matchFound = true;
                            matchType = 'Zip Code';
                            matchScore = Math.max(matchScore, 950);
                        }} else if (location.zip.startsWith(query)) {{
                            matchFound = true;
                            matchType = 'Zip Code';
                            matchScore = Math.max(matchScore, 450);
                        }}
                    }}

                    // Search full address as fallback
                    if (location.address && typeof location.address === 'string' && location.address.toLowerCase().includes(query)) {{
                        if (!matchFound) {{
                            matchFound = true;
                            matchType = 'Address';
                            matchScore = 25;
                        }}
                    }}

                    if (matchFound) {{
                        matches.push({{
                            companies: location.companies,
                            matchedCompany: matchedCompany, // Store the company that matched
                            city: location.city,
                            zip: location.zip,
                            address: location.address,
                            lat: location.lat,
                            lon: location.lon,
                            count: location.count,
                            matchType: matchType,
                            score: matchScore
                        }});
                    }}
                }});

                // Sort matches by score (highest first)
                matches.sort(function(a, b) {{
                    return b.score - a.score;
                }});

                console.log('Found matches:', matches.length);

                // Display results
                if (matches.length === 0) {{
                    resultsDiv.innerHTML = '<span style="color: #f44336;">No results found for "' + query + '"</span>';
                    return;
                }}

                // Store matches globally for pagination
                window.searchMatches = matches;
                window.searchCurrentPage = 1;
                window.searchResultsPerPage = 10;

                displaySearchResults();
            }}

            function displaySearchResults() {{
                var matches = window.searchMatches || [];
                var currentPage = window.searchCurrentPage || 1;
                var resultsPerPage = window.searchResultsPerPage || 10;
                var resultsDiv = document.getElementById('search-results');

                if (matches.length === 0) return;

                var totalPages = Math.ceil(matches.length / resultsPerPage);
                var startIdx = (currentPage - 1) * resultsPerPage;
                var endIdx = Math.min(startIdx + resultsPerPage, matches.length);

                // Clear previous results
                resultsDiv.innerHTML = '';

                // Header with count and page info
                var headerDiv = document.createElement('div');
                headerDiv.style.cssText = 'margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;';

                var countText = document.createElement('b');
                countText.textContent = matches.length + ' location(s) found';
                headerDiv.appendChild(countText);

                if (totalPages > 1) {{
                    var pageInfo = document.createElement('small');
                    pageInfo.textContent = 'Page ' + currentPage + ' of ' + totalPages;
                    headerDiv.appendChild(pageInfo);
                }}

                resultsDiv.appendChild(headerDiv);

                // Calculate bounds for all matching locations
                var bounds = [];
                for (var k = 0; k < matches.length; k++) {{
                    bounds.push([matches[k].lat, matches[k].lon]);
                }}

                // Get map object
                var mapKeys = Object.keys(window).filter(function(key) {{
                    return key.startsWith('map_') && window[key] && window[key].fitBounds;
                }});

                var mapObj = null;
                if (mapKeys.length > 0) {{
                    mapObj = window[mapKeys[0]];

                    if (bounds.length === 1) {{
                        // Single result - zoom to location
                        mapObj.setView([bounds[0][0], bounds[0][1]], 15);
                    }} else {{
                        // Multiple results - fit bounds
                        mapObj.fitBounds(bounds, {{padding: [50, 50]}});
                    }}
                }}

                // Track current highlight circle
                if (typeof window.currentHighlight === 'undefined') {{
                    window.currentHighlight = null;
                    window.highlightTimeout = null;
                }}

                // Function to clear previous highlight
                function clearPreviousHighlight() {{
                    if (window.currentHighlight && mapObj) {{
                        mapObj.removeLayer(window.currentHighlight);
                        window.currentHighlight = null;
                    }}
                    if (window.highlightTimeout) {{
                        clearTimeout(window.highlightTimeout);
                        window.highlightTimeout = null;
                    }}
                }}

                // Show results for current page
                for (var i = startIdx; i < endIdx; i++) {{
                    var match = matches[i];
                    var resultDiv = document.createElement('div');
                    resultDiv.style.cssText = 'margin: 5px 0; padding: 5px; background: #f5f5f5; border-radius: 3px; cursor: pointer;';
                    resultDiv.innerHTML = '<b>' + match.matchedCompany + '</b><br>' +
                                        '<small>' + match.city + ' ' + match.zip + ' (' + match.count + ' license' + (match.count > 1 ? 's' : '') + ')</small>';

                    // Add click handler to zoom to this specific location
                    (function(lat, lon) {{
                        resultDiv.onclick = function() {{
                            console.log('Zooming to:', lat, lon);
                            if (mapObj) {{
                                // Clear any previous highlight
                                clearPreviousHighlight();

                                // Add yellow halo circle
                                window.currentHighlight = L.circle([lat, lon], {{
                                    color: '#FFD700',        // Gold outline
                                    fill: true,
                                    fillColor: '#FFFF00',    // Yellow fill
                                    fillOpacity: 0.3,        // Transparent fill
                                    weight: 4,               // 4px outline width
                                    opacity: 0.9,            // Semi-transparent outline
                                    radius: 50               // 50 meters radius
                                }}).addTo(mapObj);

                                // Zoom to location (zoom level 15 for closer view)
                                mapObj.setView([lat, lon], 15);

                                // Fade out and remove after 10 seconds
                                window.highlightTimeout = setTimeout(function() {{
                                    if (window.currentHighlight && mapObj) {{
                                        mapObj.removeLayer(window.currentHighlight);
                                        window.currentHighlight = null;
                                    }}
                                }}, 10000);

                                // Force map to refresh tiles
                                setTimeout(function() {{
                                    mapObj.invalidateSize();
                                }}, 100);
                            }}
                        }};
                    }})(match.lat, match.lon);

                    resultsDiv.appendChild(resultDiv);
                }}

                // Add pagination controls if needed
                if (totalPages > 1) {{
                    var paginationDiv = document.createElement('div');
                    paginationDiv.style.cssText = 'margin-top: 8px; display: flex; justify-content: center; align-items: center; gap: 10px;';

                    // Previous button
                    var prevBtn = document.createElement('button');
                    prevBtn.innerHTML = '&larr;';
                    prevBtn.style.cssText = 'padding: 4px 8px; background-color: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 14px;';
                    prevBtn.disabled = currentPage === 1;
                    if (currentPage === 1) {{
                        prevBtn.style.backgroundColor = '#ccc';
                        prevBtn.style.cursor = 'not-allowed';
                    }}
                    prevBtn.onclick = function() {{
                        if (window.searchCurrentPage > 1) {{
                            window.searchCurrentPage--;
                            displaySearchResults();
                        }}
                    }};
                    paginationDiv.appendChild(prevBtn);

                    // Page indicator
                    var pageText = document.createElement('span');
                    pageText.style.cssText = 'font-size: 12px;';
                    pageText.textContent = currentPage + ' / ' + totalPages;
                    paginationDiv.appendChild(pageText);

                    // Next button
                    var nextBtn = document.createElement('button');
                    nextBtn.innerHTML = '&rarr;';
                    nextBtn.style.cssText = 'padding: 4px 8px; background-color: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 14px;';
                    nextBtn.disabled = currentPage === totalPages;
                    if (currentPage === totalPages) {{
                        nextBtn.style.backgroundColor = '#ccc';
                        nextBtn.style.cursor = 'not-allowed';
                    }}
                    nextBtn.onclick = function() {{
                        if (window.searchCurrentPage < totalPages) {{
                            window.searchCurrentPage++;
                            displaySearchResults();
                        }}
                    }};
                    paginationDiv.appendChild(nextBtn);

                    resultsDiv.appendChild(paginationDiv);
                }}
            }}

            function clearSearch() {{
                document.getElementById('search-input').value = '';
                document.getElementById('search-results').innerHTML = '';

                // Clear highlight
                if (window.currentHighlight) {{
                    var mapKeys = Object.keys(window).filter(function(key) {{
                        return key.startsWith('map_') && window[key] && window[key].removeLayer;
                    }});
                    if (mapKeys.length > 0) {{
                        var mapObj = window[mapKeys[0]];
                        mapObj.removeLayer(window.currentHighlight);
                        window.currentHighlight = null;
                    }}
                }}
                if (window.highlightTimeout) {{
                    clearTimeout(window.highlightTimeout);
                    window.highlightTimeout = null;
                }}

                // Reset map view
                var mapKeys = Object.keys(window).filter(function(key) {{
                    return key.startsWith('map_') && window[key] && window[key].setView;
                }});

                if (mapKeys.length > 0) {{
                    var mapObj = window[mapKeys[0]];
                    mapObj.setView([{MAP.CENTER_LAT}, {MAP.CENTER_LON}], {MAP.ZOOM_START});
                }}
            }}

            // Add event listeners
            document.getElementById('search-button').addEventListener('click', performSearch);
            document.getElementById('clear-search').addEventListener('click', clearSearch);

            // Allow Enter key to search
            document.getElementById('search-input').addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') {{
                    performSearch();
                }}
            }});
        }})();
        </script>
        '''

        self.map.get_root().html.add_child(folium.Element(search_html))
        logger.info("Added search control")

    def _add_custom_layer_control(self):
        """Add custom layer control with dependent Active/Inactive filtering"""
        custom_control_html = '''
        <style>
            /* Hide the overlays section of the default layer control immediately */
            .leaflet-control-layers-overlays {
                display: none !important;
            }

            /* Add black border/outline to inactive (lightgray) markers for better visibility */
            .awesome-marker-icon-lightgray i {
                text-shadow:
                    -1.5px -1.5px 0 #000,
                    1.5px -1.5px 0 #000,
                    -1.5px 1.5px 0 #000,
                    1.5px 1.5px 0 #000,
                    0 -1.5px 0 #000,
                    0 1.5px 0 #000,
                    -1.5px 0 0 #000,
                    1.5px 0 0 #000;
            }

            /* Also add a drop shadow to the marker pin itself */
            .awesome-marker-icon-lightgray {
                filter: drop-shadow(0 0 3px rgba(0, 0, 0, 0.9));
            }
        </style>

        <style>
            /* Responsive styles for Filter Licenses panel */
            @media (max-width: 768px) {
                #custom-layer-control {
                    width: 180px;
                }
                #custom-layer-control.collapsed #filter-content {
                    display: none;
                }
            }

            #custom-layer-control.collapsed #filter-content {
                display: none;
            }
        </style>

        <div id="custom-layer-control" style="position: fixed;
                    top: 80px; right: 10px; width: 220px;
                    background-color: white; border: 2px solid rgba(0,0,0,0.2);
                    border-radius: 4px;
                    z-index: 1000; font-size: 13px; padding: 10px;
                    font-family: Arial, sans-serif;
                    box-shadow: 0 1px 5px rgba(0,0,0,0.4);">
            <div style="margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #ccc; display: flex; justify-content: space-between; align-items: center;">
                <b>Filter Licenses</b>
                <button id="toggle-filter-btn" title="Collapse/Expand" style="background: none; border: none; cursor: pointer; padding: 0; font-size: 14px; color: #666;">
                    <i class="fa fa-chevron-up"></i>
                </button>
            </div>
            <div id="filter-content">

            <!-- Active/Inactive filters -->
            <div style="margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #eee;">
                <label style="display: inline-block; margin-right: 10px; cursor: pointer;">
                    <input type="checkbox" id="filter-active" checked style="cursor: pointer;"> Active
                </label>
                <label style="display: inline-block; cursor: pointer;">
                    <input type="checkbox" id="filter-inactive" checked style="cursor: pointer;"> Inactive
                </label>
            </div>

            <!-- License type filters with icons on the right -->
            <div>
                <label style="display: flex; justify-content: space-between; align-items: center; margin: 5px 0; cursor: pointer;">
                    <span><input type="checkbox" class="license-type" data-category="Grower" checked style="cursor: pointer; margin-right: 5px;"> Growers</span>
                    <i class="fa fa-leaf" style="color:#2D5016; font-size: 16px;"></i>
                </label>
                <label style="display: flex; justify-content: space-between; align-items: center; margin: 5px 0; cursor: pointer;">
                    <span><input type="checkbox" class="license-type" data-category="Processor" checked style="cursor: pointer; margin-right: 5px;"> Processors</span>
                    <i class="fa fa-flask" style="color:#1565C0; font-size: 16px;"></i>
                </label>
                <label style="display: flex; justify-content: space-between; align-items: center; margin: 5px 0; cursor: pointer;">
                    <span><input type="checkbox" class="license-type" data-category="Retailer" checked style="cursor: pointer; margin-right: 5px;"> Retailers</span>
                    <i class="fa fa-shopping-cart" style="color:#6A1B9A; font-size: 16px;"></i>
                </label>
                <label style="display: flex; justify-content: space-between; align-items: center; margin: 5px 0; cursor: pointer;">
                    <span><input type="checkbox" class="license-type" data-category="Transporter" checked style="cursor: pointer; margin-right: 5px;"> Transporters</span>
                    <i class="fa fa-truck" style="color:#E65100; font-size: 16px;"></i>
                </label>
            </div>

            <!-- For Sale filter (bright fluorescent green) -->
            <div style="margin-top: 10px; padding-top: 8px; padding-bottom: 8px; border-top: 1px solid #eee; border-bottom: 1px solid #eee;">
                <label style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;">
                    <span style="font-weight: bold; color: #39FF14;"><input type="checkbox" id="filter-forsale" checked style="cursor: pointer; margin-right: 5px;"> Retail - For Sale</span>
                    <i class="fa fa-dollar-sign" style="color: #39FF14; font-size: 18px; text-shadow: 0 0 3px #39FF14;"></i>
                </label>
            </div>

            <!-- Inactive/Closed indicator -->
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 12px; color: #666;">Inactive/Closed</span>
                    <i class="fa fa-circle" style="color:#BDBDBD; font-size: 12px;"></i>
                </div>
            </div>
            </div>
        </div>

        <script>
        (function() {
            // Toggle button functionality
            var toggleBtn = document.getElementById('toggle-filter-btn');
            var filterControl = document.getElementById('custom-layer-control');
            var toggleIcon = toggleBtn.querySelector('i');

            toggleBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                filterControl.classList.toggle('collapsed');

                // Update icon
                if (filterControl.classList.contains('collapsed')) {
                    toggleIcon.className = 'fa fa-chevron-down';
                } else {
                    toggleIcon.className = 'fa fa-chevron-up';
                }

                // Mark as manually toggled to prevent auto-collapse from overriding
                filterControl.setAttribute('data-manual-toggle', 'true');
            });

            // Auto-collapse on mobile/tablet (< 768px)
            var handleResponsiveCollapse = function() {
                var isMobile = window.innerWidth < 768;
                var isManuallyToggled = filterControl.getAttribute('data-manual-toggle') === 'true';

                // Only auto-collapse/expand if user hasn't manually toggled
                if (!isManuallyToggled) {
                    if (isMobile && !filterControl.classList.contains('collapsed')) {
                        filterControl.classList.add('collapsed');
                        toggleIcon.className = 'fa fa-chevron-down';
                    } else if (!isMobile && filterControl.classList.contains('collapsed')) {
                        filterControl.classList.remove('collapsed');
                        toggleIcon.className = 'fa fa-chevron-up';
                    }
                }
            };

            // Run on load
            handleResponsiveCollapse();

            // Run on window resize (debounced)
            var resizeTimer;
            window.addEventListener('resize', function() {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(handleResponsiveCollapse, 250);
            });

            // Wait for map to be fully loaded
            var initCustomControl = function() {
                // Find the map object and layer control
                var mapObj = null;
                var layerControlObj = null;

                var mapKeys = Object.keys(window).filter(function(key) {
                    return key.startsWith('map_') && window[key] && window[key]._layers;
                });

                if (mapKeys.length === 0) {
                    setTimeout(initCustomControl, 100);
                    return;
                }

                mapObj = window[mapKeys[0]];

                // Find the layer control
                var layerControlKeys = Object.keys(window).filter(function(key) {
                    return key.match(/^layer_control_/) && window[key];
                });

                if (layerControlKeys.length > 0) {
                    layerControlObj = window[layerControlKeys[0]];
                }

                // Store all feature groups by name
                var layerGroups = {};

                // Get layers from layer control's overlays object
                if (layerControlObj && layerControlObj.overlays) {
                    Object.keys(layerControlObj.overlays).forEach(function(layerName) {
                        layerGroups[layerName] = layerControlObj.overlays[layerName];
                    });
                }

                console.log('Found layer groups:', Object.keys(layerGroups));
                console.log('Total layers found:', Object.keys(layerGroups).length);

                // Function to update layer visibility
                function updateLayers() {
                    var activeChecked = document.getElementById('filter-active').checked;
                    var inactiveChecked = document.getElementById('filter-inactive').checked;
                    var licenseTypes = document.querySelectorAll('.license-type');

                    licenseTypes.forEach(function(checkbox) {
                        var category = checkbox.getAttribute('data-category');
                        var typeChecked = checkbox.checked;

                        // Handle both AU and MED market types for this category
                        ['AU', 'MED'].forEach(function(market) {
                            var activeLayerName = 'Active - ' + category + 's (' + market + ')';
                            var inactiveLayerName = 'Inactive - ' + category + 's (' + market + ')';

                            // Control active layer
                            var activeLayer = layerGroups[activeLayerName];
                            if (activeLayer) {
                                if (activeChecked && typeChecked) {
                                    mapObj.addLayer(activeLayer);
                                } else {
                                    mapObj.removeLayer(activeLayer);
                                }
                            }

                            // Control inactive layer
                            var inactiveLayer = layerGroups[inactiveLayerName];
                            if (inactiveLayer) {
                                if (inactiveChecked && typeChecked) {
                                    mapObj.addLayer(inactiveLayer);
                                } else {
                                    mapObj.removeLayer(inactiveLayer);
                                }
                            }
                        });
                    });
                }

                // Function to update For Sale layer visibility
                function updateForSaleLayer() {
                    var forsaleChecked = document.getElementById('filter-forsale').checked;
                    var forsaleLayer = layerGroups['Retail - For Sale'];

                    if (forsaleLayer) {
                        if (forsaleChecked) {
                            mapObj.addLayer(forsaleLayer);
                        } else {
                            mapObj.removeLayer(forsaleLayer);
                        }
                    }
                }

                // Add event listeners
                document.getElementById('filter-active').addEventListener('change', updateLayers);
                document.getElementById('filter-inactive').addEventListener('change', updateLayers);
                document.getElementById('filter-forsale').addEventListener('change', updateForSaleLayer);

                document.querySelectorAll('.license-type').forEach(function(checkbox) {
                    checkbox.addEventListener('change', updateLayers);
                });

                // Initial update to set correct state
                updateLayers();
                updateForSaleLayer();
            };

            // Start initialization when DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    setTimeout(initCustomControl, 500);
                });
            } else {
                setTimeout(initCustomControl, 500);
            }
        })();
        </script>
        '''
        self.map.get_root().html.add_child(folium.Element(custom_control_html))
        logger.info("Added custom layer control with dependent filtering")

    def _add_footer(self):
        """Add footer with attribution and link"""
        footer_html = '''
        <div style="position: fixed;
                    bottom: 10px; left: 50%; transform: translateX(-50%);
                    background-color: white; border: 1px solid rgba(0,0,0,0.2);
                    border-radius: 4px;
                    z-index: 1000; font-size: 12px; padding: 8px 15px;
                    font-family: Arial, sans-serif;
                    box-shadow: 0 1px 5px rgba(0,0,0,0.2);">
            Map by Southpaw Strategies. <a href="https://spstrat.com/#" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: bold;">Wholesale cannabis</a> delivered at 40% off market price.
        </div>

        <!-- Visit Counter -->
        <div id="visit-counter" style="position: fixed;
                    bottom: 10px; right: 10px;
                    background-color: white; border: 1px solid rgba(0,0,0,0.2);
                    border-radius: 4px;
                    z-index: 1000; font-size: 11px; padding: 5px 10px;
                    font-family: Arial, sans-serif;
                    box-shadow: 0 1px 5px rgba(0,0,0,0.2);
                    color: #666;">
            <i class="fa fa-eye" style="margin-right: 5px;"></i>
            <span id="visit-count">Loading...</span> visits
        </div>

        <script>
        (function() {
            // Visit counter using countapi.xyz
            var counterKey = 'michigan-cannabis-map';
            var counterNamespace = 'spstrat';

            // Increment and get count
            fetch('https://api.countapi.xyz/hit/' + counterNamespace + '/' + counterKey)
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data && data.value) {
                        document.getElementById('visit-count').textContent = data.value.toLocaleString();
                    } else {
                        document.getElementById('visit-count').textContent = '---';
                    }
                })
                .catch(function(error) {
                    console.error('Error loading visit counter:', error);
                    document.getElementById('visit-count').textContent = '---';
                });
        })();
        </script>
        '''
        self.map.get_root().html.add_child(folium.Element(footer_html))
        logger.info("Added footer")

    def _add_favicon(self):
        """Add favicon to the map HTML as embedded base64 data URI"""
        import base64
        from pathlib import Path

        # Read and encode favicon as base64
        favicon_path = Path('favicon.jpg')
        if favicon_path.exists():
            with open(favicon_path, 'rb') as f:
                favicon_data = base64.b64encode(f.read()).decode('utf-8')
            favicon_html = f'<link rel="icon" type="image/jpeg" href="data:image/jpeg;base64,{favicon_data}">'
            self.map.get_root().header.add_child(folium.Element(favicon_html))
            logger.info("Added favicon (embedded as base64)")
        else:
            logger.warning("Favicon file not found, skipping")

    def _save_map(self, output_file: str):
        """Save map to HTML file"""
        from pathlib import Path
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.map.save(str(output_path))
        logger.info(f"Map saved to: {output_path}")
