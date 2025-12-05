"""
Script to generate interactive Folium map from geocoded data.

Usage:
    python generate_map.py
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.map_generator import MapGenerator


def main():
    """Main entry point"""
    print("=== Michigan Cannabis License Map ===")
    print("=== Phase 4: Map Generation ===\n")

    input_file = 'data/processed/geocoded_licenses.csv'
    output_file = 'output/michigan_cannabis_map.html'

    # Check if input file exists
    if not Path(input_file).exists():
        print(f"[ERROR] Input file not found: {input_file}")
        print("Please run 'python geocode_addresses.py' first")
        sys.exit(1)

    try:
        # Load geocoded data
        print(f"Loading geocoded data from: {input_file}")
        df = pd.read_csv(input_file)
        print(f"Loaded {len(df)} records\n")

        # Show geocoding statistics
        total = len(df)
        success = (df['geocode_status'] == 'success').sum()
        success_rate = (success / total * 100) if total > 0 else 0
        print(f"Geocoding success rate: {success_rate:.1f}% ({success}/{total})")
        print(f"Will create map with {success} geocoded locations\n")

        # Initialize map generator
        generator = MapGenerator()

        # Generate map
        print("Generating interactive map...")
        map_obj = generator.generate_map(df, output_file=output_file)

        print(f"\n[SUCCESS] Map generated successfully!")
        print(f"[SUCCESS] Saved to: {output_file}")
        print(f"\nTo view the map:")
        print(f"1. Open index.html in your browser, OR")
        print(f"2. Open {output_file} directly in your browser")

    except Exception as e:
        print(f"\n[ERROR] Map generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
