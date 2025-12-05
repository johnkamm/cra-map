"""
Script to geocode addresses from consolidated CSV.

Usage:
    python geocode_addresses.py              # Geocode all addresses (~2 hours)
    python geocode_addresses.py --test       # Test mode: first 100 addresses only
    python geocode_addresses.py --test --limit 50  # Test with custom limit
"""

import sys
import argparse
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.geocoder import GeocodingService


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Geocode cannabis license addresses')
    parser.add_argument('--test', action='store_true', help='Test mode: geocode limited records')
    parser.add_argument('--limit', type=int, default=100, help='Number of records in test mode')
    args = parser.parse_args()

    print("=== Michigan Cannabis License Map ===")
    print("=== Phase 2: Geocoding Addresses ===\n")

    input_file = 'data/processed/consolidated_licenses.csv'
    output_file = 'data/processed/geocoded_licenses.csv'

    # Check if input file exists
    if not Path(input_file).exists():
        print(f"[ERROR] Input file not found: {input_file}")
        print("Please run 'python consolidate_csv.py' first")
        sys.exit(1)

    try:
        # Load consolidated data
        print(f"Loading data from: {input_file}")
        df = pd.read_csv(input_file)
        print(f"Loaded {len(df)} records\n")

        if args.test:
            print(f"[TEST MODE] Will geocode first {args.limit} records")
            print("This is recommended before running full geocoding\n")

        # Initialize geocoder
        geocoder = GeocodingService()

        # Geocode addresses
        print("Starting geocoding process...")
        if args.test:
            print(f"Estimated time: {args.limit} seconds (1 req/sec)")
        else:
            print(f"Estimated time: ~{len(df) // 3600} hours ({len(df)} addresses @ 1 req/sec)")
        print()

        df_geocoded = geocoder.geocode_dataframe(df, test_mode=args.test, test_limit=args.limit)

        # Save results
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_geocoded.to_csv(output_path, index=False)

        print(f"\n[SUCCESS] Geocoded data saved to: {output_file}")

        # Show success rate
        success_count = (df_geocoded['geocode_status'] == 'success').sum()
        success_rate = (success_count / len(df_geocoded) * 100)
        print(f"[SUCCESS] Geocoding success rate: {success_rate:.1f}% ({success_count}/{len(df_geocoded)})")

        if args.test:
            print("\n[INFO] This was a test run")
            print("To geocode all addresses, run: python geocode_addresses.py")
        else:
            print("\nNext step: Run 'python generate_map.py' to create the map")

    except KeyboardInterrupt:
        print("\n\n[INFO] Geocoding interrupted by user")
        print("[INFO] Progress has been saved to cache")
        print("[INFO] Run the script again to resume from where you left off")
        sys.exit(0)

    except Exception as e:
        print(f"\n[ERROR] Geocoding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
