"""
Script to re-geocode city-level addresses using ArcGIS fallback.

This script:
1. Loads existing geocoded data
2. Identifies addresses with city-level precision (fallback)
3. Clears cache entries for those addresses
4. Re-geocodes them with the new ArcGIS fallback
5. Merges improved results back into the full dataset
6. Saves the updated file
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
    print("=== Re-geocode City-Level Addresses ===\n")

    input_file = 'data/processed/geocoded_licenses.csv'
    output_file = 'data/processed/geocoded_licenses.csv'
    cache_file = 'data/cache/geocode_cache.json'

    # Check if input file exists
    if not Path(input_file).exists():
        print(f"[ERROR] Input file not found: {input_file}")
        sys.exit(1)

    try:
        # Load existing geocoded data
        print(f"Loading geocoded data from: {input_file}")
        df = pd.read_csv(input_file)
        print(f"Loaded {len(df)} total records\n")

        # Filter to city-level precision records
        city_level_df = df[df['geocode_precision'] == 'city'].copy()
        print(f"Found {len(city_level_df)} city-level addresses to re-geocode")
        print(f"Keeping {len(df) - len(city_level_df)} address-level results\n")

        if len(city_level_df) == 0:
            print("No city-level addresses to re-geocode!")
            return

        # Initialize geocoding service
        geocoder = GeocodingService(cache_file=cache_file)

        # Clear cache entries for city-level addresses
        print("Clearing cache entries for city-level addresses...")
        addresses_to_clear = city_level_df['address'].dropna().unique()
        cleared_count = 0
        for address in addresses_to_clear:
            if address in geocoder.cache:
                del geocoder.cache[address]
                cleared_count += 1
        geocoder._save_cache()
        print(f"Cleared {cleared_count} cache entries\n")

        # Re-geocode city-level addresses
        print(f"Re-geocoding {len(city_level_df)} addresses with ArcGIS fallback...")
        print("This will take approximately 35 minutes due to rate limiting...\n")

        regeocoded_df = geocoder.geocode_dataframe(city_level_df)

        # Count improvements
        improved = (regeocoded_df['geocode_precision'] == 'address').sum()
        still_city = (regeocoded_df['geocode_precision'] == 'city').sum()
        print(f"\n=== RE-GEOCODING RESULTS ===")
        print(f"Improved to address-level: {improved} ({improved/len(regeocoded_df)*100:.1f}%)")
        print(f"Still city-level: {still_city} ({still_city/len(regeocoded_df)*100:.1f}%)")

        # Show source breakdown for improved addresses
        improved_df = regeocoded_df[regeocoded_df['geocode_precision'] == 'address']
        if len(improved_df) > 0:
            print(f"\nImproved addresses by source:")
            source_counts = improved_df['geocode_source'].value_counts()
            for source, count in source_counts.items():
                print(f"  {source}: {count}")

        # Merge results back into full dataset
        print("\nMerging results back into full dataset...")
        # Update the city-level rows with re-geocoded results
        for idx in city_level_df.index:
            if idx in regeocoded_df.index:
                df.loc[idx] = regeocoded_df.loc[idx]

        # Calculate new overall statistics
        total = len(df)
        address_level = (df['geocode_precision'] == 'address').sum()
        city_level = (df['geocode_precision'] == 'city').sum()
        success_rate = (address_level / total * 100) if total > 0 else 0

        print(f"\n=== OVERALL STATISTICS ===")
        print(f"Total records: {total}")
        print(f"Address-level: {address_level} ({success_rate:.1f}%)")
        print(f"City-level: {city_level} ({city_level/total*100:.1f}%)")

        # Save updated file
        print(f"\nSaving updated data to: {output_file}")
        df.to_csv(output_file, index=False)

        print(f"\n[SUCCESS] Re-geocoding complete!")
        print(f"[SUCCESS] Updated file saved to: {output_file}")
        print(f"\nNext step: Run 'python generate_map.py' to update the map")

    except Exception as e:
        print(f"\n[ERROR] Re-geocoding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
