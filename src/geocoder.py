"""
Geocoding module for Michigan Cannabis License Map
Handles address geocoding with caching, rate limiting, and fallback strategies
"""

import pandas as pd
from geopy.geocoders import Nominatim, GoogleV3, Photon, ArcGIS
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
import time
import json
from pathlib import Path
from typing import Dict, Optional
import logging
from tqdm import tqdm

from .config import GEOCODING, MI_LAT_MIN, MI_LAT_MAX, MI_LON_MIN, MI_LON_MAX

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeocodingService:
    """Geocoding service with caching, rate limiting, and fallback"""

    def __init__(self, cache_file: str = None, google_api_key: str = None):
        """
        Initialize geocoding service.

        Args:
            cache_file: Path to cache file (JSON)
            google_api_key: Optional Google Maps API key for better accuracy
        """
        self.cache_file = Path(cache_file or GEOCODING.CACHE_FILE)

        # Initialize geocoders
        self.geolocator = Nominatim(user_agent=GEOCODING.USER_AGENT, timeout=GEOCODING.TIMEOUT)
        self.photon = Photon(user_agent=GEOCODING.USER_AGENT, timeout=GEOCODING.TIMEOUT)
        self.arcgis = ArcGIS(user_agent=GEOCODING.USER_AGENT, timeout=GEOCODING.TIMEOUT)
        logger.info("Multi-service geocoding: ArcGIS (primary) + Nominatim + Photon (fallbacks)")

        # Initialize Google geocoder if API key provided
        self.google_geocoder = None
        if google_api_key:
            self.google_geocoder = GoogleV3(api_key=google_api_key, timeout=GEOCODING.TIMEOUT)
            logger.info("Google Maps geocoding also enabled (hybrid mode)")

        self.cache = self._load_cache()
        self.rate_limit = GEOCODING.RATE_LIMIT
        self.checkpoint_interval = GEOCODING.CHECKPOINT_INTERVAL
        self.requests_count = 0
        self.google_requests = 0  # Track Google API usage

    def _load_cache(self) -> Dict:
        """Load existing geocoding cache from JSON file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                logger.info(f"Loaded {len(cache)} cached geocoding results")
                return cache
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}. Starting with empty cache.")
                return {}
        return {}

    def _save_cache(self):
        """Persist cache to disk"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _extract_city(self, address: str) -> Optional[str]:
        """
        Extract city name from address format: 'Street, City MI Zip'

        Args:
            address: Full address string

        Returns:
            City name or None
        """
        try:
            parts = address.split(',')
            if len(parts) >= 2:
                city_state_zip = parts[1].strip()
                city = city_state_zip.split(' MI ')[0].strip()
                return city
        except Exception:
            pass
        return None

    def _is_valid_michigan_coords(self, lat: float, lon: float) -> bool:
        """
        Check if coordinates are within Michigan bounds.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if within Michigan bounds
        """
        return (MI_LAT_MIN <= lat <= MI_LAT_MAX) and (MI_LON_MIN <= lon <= MI_LON_MAX)

    def geocode_address(self, address: str) -> Dict:
        """
        Geocode a single address with caching and rate limiting.

        Args:
            address: Address string to geocode

        Returns:
            Dictionary with geocoding results
        """
        # Check cache first
        if address in self.cache:
            return self.cache[address]

        # Rate limiting
        if self.requests_count > 0:
            time.sleep(self.rate_limit)

        # Attempt 1: ArcGIS (best US coverage and accuracy)
        result = self._geocode_with_arcgis(f"{address}, Michigan, USA")

        if result['status'] == 'success':
            result['precision'] = 'address'
            result['source'] = 'arcgis'
        else:
            # Attempt 2: Nominatim (free, OSM-based)
            result = self._geocode_with_retry(f"{address}, Michigan, USA")
            if result['status'] == 'success':
                result['precision'] = 'address'
                result['source'] = 'nominatim'
                return self._cache_and_return(address, result)

            # Attempt 3: Photon (free, alternative OSM geocoder)
            result = self._geocode_with_photon(f"{address}, Michigan, USA")
            if result['status'] == 'success':
                result['precision'] = 'address'
                result['source'] = 'photon'
                return self._cache_and_return(address, result)

            # Attempt 4: Google Maps API if available (more accurate but paid)
            if self.google_geocoder:
                result = self._geocode_with_google(f"{address}, Michigan, USA")
                if result['status'] == 'success':
                    result['precision'] = 'address'
                    result['source'] = 'google'
                    self.google_requests += 1
                    return self._cache_and_return(address, result)

            # Final fallback: city-level geocoding with Nominatim
            city = self._extract_city(address)
            if city:
                result = self._geocode_with_retry(f"{city}, Michigan, USA")
                if result['status'] == 'success':
                    result['precision'] = 'city'
                    result['source'] = 'nominatim_city'
                    logger.warning(f"Geocoded to city level: {address} -> {city}")
                else:
                    result['precision'] = 'failed'
            else:
                result['precision'] = 'failed'

        # Cache result
        self.cache[address] = result
        self.requests_count += 1

        # Periodic checkpoint save
        if self.requests_count % self.checkpoint_interval == 0:
            self._save_cache()
            logger.info(f"Checkpoint: Saved cache after {self.requests_count} requests")

        return result

    def _geocode_with_retry(self, query: str, retries: int = 2) -> Dict:
        """
        Geocode with retry logic.

        Args:
            query: Query string to geocode
            retries: Number of retries on failure

        Returns:
            Geocoding result dictionary
        """
        for attempt in range(retries + 1):
            try:
                location = self.geolocator.geocode(query)

                if location:
                    lat, lon = location.latitude, location.longitude

                    # Validate coordinates are in Michigan
                    if self._is_valid_michigan_coords(lat, lon):
                        return {
                            'latitude': lat,
                            'longitude': lon,
                            'status': 'success'
                        }
                    else:
                        logger.warning(f"Coordinates outside Michigan bounds: {query} -> ({lat}, {lon})")
                        return {'status': 'out_of_bounds'}

                # No location found
                return {'status': 'not_found'}

            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                if attempt < retries:
                    logger.warning(f"Geocoding timeout, retry {attempt + 1}/{retries}: {query}")
                    time.sleep(2)
                else:
                    logger.error(f"Geocoding failed after {retries} retries: {query}")
                    return {'status': 'error', 'message': str(e)}

            except GeocoderServiceError as e:
                logger.error(f"Geocoder service error: {query} - {e}")
                return {'status': 'error', 'message': str(e)}

            except Exception as e:
                logger.error(f"Unexpected geocoding error: {query} - {e}")
                return {'status': 'error', 'message': str(e)}

        return {'status': 'failed'}

    def _geocode_with_photon(self, query: str) -> Dict:
        """
        Geocode using Photon (alternative OSM geocoder).

        Args:
            query: Address query to geocode

        Returns:
            Geocoding result dictionary
        """
        try:
            location = self.photon.geocode(query)

            if location:
                lat, lon = location.latitude, location.longitude

                # Validate coordinates are in Michigan
                if self._is_valid_michigan_coords(lat, lon):
                    logger.info(f"Photon geocoded: {query}")
                    return {
                        'latitude': lat,
                        'longitude': lon,
                        'status': 'success'
                    }
                else:
                    logger.warning(f"Photon: Coordinates outside Michigan bounds: {query}")
                    return {'status': 'out_of_bounds'}

            return {'status': 'not_found'}

        except Exception as e:
            logger.error(f"Photon geocoding error: {query} - {e}")
            return {'status': 'error', 'message': str(e)}

    def _geocode_with_arcgis(self, query: str) -> Dict:
        """
        Geocode using ArcGIS (free tier with good US coverage).

        Args:
            query: Address query to geocode

        Returns:
            Geocoding result dictionary
        """
        try:
            location = self.arcgis.geocode(query)

            if location:
                lat, lon = location.latitude, location.longitude

                # Validate coordinates are in Michigan
                if self._is_valid_michigan_coords(lat, lon):
                    logger.info(f"ArcGIS geocoded: {query}")
                    return {
                        'latitude': lat,
                        'longitude': lon,
                        'status': 'success'
                    }
                else:
                    logger.warning(f"ArcGIS: Coordinates outside Michigan bounds: {query}")
                    return {'status': 'out_of_bounds'}

            return {'status': 'not_found'}

        except Exception as e:
            logger.error(f"ArcGIS geocoding error: {query} - {e}")
            return {'status': 'error', 'message': str(e)}

    def _geocode_with_google(self, query: str) -> Dict:
        """
        Geocode using Google Maps API.

        Args:
            query: Address query to geocode

        Returns:
            Geocoding result dictionary
        """
        try:
            location = self.google_geocoder.geocode(query)

            if location:
                lat, lon = location.latitude, location.longitude

                # Validate coordinates are in Michigan
                if self._is_valid_michigan_coords(lat, lon):
                    logger.info(f"Google geocoded: {query}")
                    return {
                        'latitude': lat,
                        'longitude': lon,
                        'status': 'success'
                    }
                else:
                    logger.warning(f"Google: Coordinates outside Michigan bounds: {query}")
                    return {'status': 'out_of_bounds'}

            return {'status': 'not_found'}

        except Exception as e:
            logger.error(f"Google geocoding error: {query} - {e}")
            return {'status': 'error', 'message': str(e)}

    def _cache_and_return(self, address: str, result: Dict) -> Dict:
        """Cache result and return it"""
        self.cache[address] = result
        self.requests_count += 1

        # Periodic checkpoint save
        if self.requests_count % self.checkpoint_interval == 0:
            self._save_cache()
            logger.info(f"Checkpoint: Saved cache after {self.requests_count} requests")

        return result

    def geocode_dataframe(self, df: pd.DataFrame, test_mode: bool = False, test_limit: int = 100) -> pd.DataFrame:
        """
        Geocode all addresses in a DataFrame.

        Args:
            df: DataFrame with 'address' column
            test_mode: If True, only geocode first test_limit records
            test_limit: Number of records to geocode in test mode

        Returns:
            DataFrame with added latitude, longitude, geocode_status, geocode_precision columns
        """
        if test_mode:
            logger.info(f"TEST MODE: Geocoding first {test_limit} records only")
            df = df.head(test_limit).copy()
        else:
            df = df.copy()

        # Initialize result columns
        df['latitude'] = None
        df['longitude'] = None
        df['geocode_status'] = None
        df['geocode_precision'] = None
        df['geocode_source'] = None

        # Geocode each address
        logger.info(f"Starting geocoding for {len(df)} addresses...")

        with tqdm(total=len(df), desc="Geocoding", unit="address") as pbar:
            for idx, row in df.iterrows():
                address = row['address']

                if pd.isna(address):
                    df.at[idx, 'geocode_status'] = 'no_address'
                    df.at[idx, 'geocode_precision'] = 'failed'
                    pbar.update(1)
                    continue

                result = self.geocode_address(address)

                df.at[idx, 'geocode_status'] = result['status']
                df.at[idx, 'geocode_precision'] = result.get('precision', 'unknown')
                df.at[idx, 'geocode_source'] = result.get('source', None)

                if result['status'] == 'success':
                    df.at[idx, 'latitude'] = result['latitude']
                    df.at[idx, 'longitude'] = result['longitude']

                pbar.update(1)

        # Final cache save
        self._save_cache()
        logger.info(f"Final cache saved with {len(self.cache)} entries")

        # Print summary
        self._print_geocoding_summary(df)

        return df

    def _print_geocoding_summary(self, df: pd.DataFrame):
        """Print geocoding statistics"""
        total = len(df)
        success = (df['geocode_status'] == 'success').sum()
        success_rate = (success / total * 100) if total > 0 else 0

        logger.info("\n=== GEOCODING SUMMARY ===")
        logger.info(f"Total Addresses: {total}")
        logger.info(f"Successfully Geocoded: {success} ({success_rate:.1f}%)")

        precision_counts = df['geocode_precision'].value_counts()
        logger.info("\nPrecision Levels:")
        for precision, count in precision_counts.items():
            logger.info(f"  {precision}: {count}")

        # Show source breakdown if available
        if 'geocode_source' in df.columns:
            source_counts = df['geocode_source'].value_counts()
            logger.info("\nGeocoding Sources:")
            for source, count in source_counts.items():
                if pd.notna(source):
                    logger.info(f"  {source}: {count}")

        status_counts = df['geocode_status'].value_counts()
        logger.info("\nStatus Distribution:")
        for status, count in status_counts.items():
            logger.info(f"  {status}: {count}")

        # Show Google API usage if enabled
        if self.google_requests > 0:
            cost_estimate = (self.google_requests / 1000) * 5
            logger.info(f"\nGoogle Maps API Usage:")
            logger.info(f"  Requests: {self.google_requests}")
            logger.info(f"  Estimated Cost: ${cost_estimate:.2f}")

        logger.info("=" * 30 + "\n")
