"""
Script to fix addresses that were incorrectly geocoded to the same coordinates.
"""

import sys
from pathlib import Path
import pandas as pd
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.geocoder import GeocodingService


def main():
    """Main entry point"""
    print("=== Fix Duplicate Coordinates ===\n")

    input_file = 'data/processed/geocoded_licenses.csv'
    output_file = 'data/processed/geocoded_licenses.csv'
    cache_file = 'data/cache/geocode_cache.json'

    # Load data
    print(f"Loading geocoded data from: {input_file}")
    df = pd.read_csv(input_file)

    # Find all addresses with coordinates 43.571561, -86.032414 (within tolerance)
    problem_coords = (43.571561, -86.032414)
    tolerance = 0.000001
    problem_addresses = df[
        (abs(df['latitude'] - problem_coords[0]) < tolerance) &
        (abs(df['longitude'] - problem_coords[1]) < tolerance) &
        (df['address'].str.contains('Hesperia', na=False))
    ]['address'].unique()

    print(f"Found {len(problem_addresses)} unique addresses with duplicate coordinates:")
    for addr in problem_addresses:
        print(f"  - {addr}")

    # Initialize geocoding service
    geocoder = GeocodingService(cache_file=cache_file)

    # Clear cache for these addresses
    print("\nClearing cache entries...")
    for address in problem_addresses:
        if address in geocoder.cache:
            del geocoder.cache[address]
    geocoder._save_cache()

    # Re-geocode each address directly with ArcGIS (skip Nominatim and Photon)
    print(f"\nRe-geocoding {len(problem_addresses)} addresses directly with ArcGIS...\n")

    results = {}
    for address in problem_addresses:
        print(f"Re-geocoding: {address}")
        # Call ArcGIS directly
        result = geocoder._geocode_with_arcgis(f"{address}, Michigan, USA")
        if result['status'] == 'success':
            result['precision'] = 'address'
            result['source'] = 'arcgis'
            print(f"  [OK] Success: {result['latitude']}, {result['longitude']} (source: arcgis)")
        else:
            print(f"  [FAIL] Failed: {result['status']}")
        results[address] = result

        # Save to cache
        geocoder.cache[address] = result

    geocoder._save_cache()

    # Update the dataframe
    print("\nUpdating records in dataset...")
    for address, result in results.items():
        if result['status'] == 'success':
            mask = df['address'] == address
            df.loc[mask, 'latitude'] = result['latitude']
            df.loc[mask, 'longitude'] = result['longitude']
            df.loc[mask, 'geocode_precision'] = result.get('precision', 'address')
            df.loc[mask, 'geocode_source'] = result.get('source', 'arcgis')

    # Save updated file
    print(f"\nSaving updated data to: {output_file}")
    df.to_csv(output_file, index=False)

    print("\n[SUCCESS] Fixed duplicate coordinates!")
    print("Next step: Run 'python generate_map.py' to update the map")


if __name__ == '__main__':
    main()
