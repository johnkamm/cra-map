"""
Script to consolidate all CSV files into a single unified dataset.

Usage:
    python consolidate_csv.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.consolidator import DataConsolidator


def main():
    """Main entry point"""
    print("=== Michigan Cannabis License Map ===")
    print("=== Phase 1: Data Consolidation ===\n")

    try:
        # Initialize consolidator
        consolidator = DataConsolidator(data_dir='CRA Lists')

        # Run consolidation
        df = consolidator.consolidate(output_file='data/processed/consolidated_licenses.csv')

        print(f"\n[SUCCESS] Consolidated {len(df)} records")
        print("[SUCCESS] Output saved to: data/processed/consolidated_licenses.csv")
        print("\nNext step: Run 'python geocode_addresses.py' to geocode addresses")

    except Exception as e:
        print(f"\n[ERROR] Consolidation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
