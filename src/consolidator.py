"""
Data consolidation module for Michigan Cannabis License Map
Handles reading 14 CSV files and consolidating into unified schema
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataConsolidator:
    """Consolidate 14 CSV files into unified schema"""

    # Column mapping for AU vs MED files
    COLUMN_MAPPING = {
        'AU': {
            'Record Number': 'record_number',
            'Record Type': 'record_type',
            'License Name': 'business_name',  # KEY DIFFERENCE
            'Address': 'address',
            'Expiration Date': 'expiration_date',
            'Status': 'status',
            'Notes': 'notes',
            'Disciplinary Action': 'disciplinary_action'
        },
        'MED': {
            'Record Number': 'record_number',
            'Record Type': 'record_type',
            'Licensee Name': 'business_name',  # KEY DIFFERENCE
            'Address': 'address',
            'Expiration Date': 'expiration_date',
            'Status': 'status',
            'Home Delivery': 'home_delivery',  # KEY DIFFERENCE
            'Disciplinary Action': 'disciplinary_action'
        }
    }

    def __init__(self, data_dir: str = 'CRA Lists'):
        """
        Initialize consolidator.

        Args:
            data_dir: Directory containing the 14 CSV files
        """
        self.data_dir = Path(data_dir)

    def consolidate(self, output_file: str = 'data/processed/consolidated_licenses.csv') -> pd.DataFrame:
        """
        Load and consolidate all CSV files.

        Args:
            output_file: Path to save consolidated CSV

        Returns:
            Consolidated DataFrame
        """
        logger.info(f"Starting consolidation from {self.data_dir}")

        all_data = []
        csv_files = list(self.data_dir.glob('*.csv'))

        if not csv_files:
            logger.error(f"No CSV files found in {self.data_dir}")
            raise FileNotFoundError(f"No CSV files found in {self.data_dir}")

        logger.info(f"Found {len(csv_files)} CSV files")

        for csv_file in csv_files:
            try:
                logger.info(f"Processing: {csv_file.name}")

                # Determine program type from filename
                program_type = 'AU' if csv_file.name.startswith('AU') else 'MED'

                # Determine license category and class
                license_info = self._parse_filename(csv_file.name)

                # Load CSV
                df = pd.read_csv(csv_file)
                logger.info(f"  Loaded {len(df)} records")

                # Apply column mapping
                mapping = self.COLUMN_MAPPING[program_type]
                df = df.rename(columns=mapping)

                # Add metadata columns
                df['program_type'] = program_type
                df['license_category'] = license_info['category']
                df['license_class'] = license_info.get('class', None)
                df['source_file'] = csv_file.name

                all_data.append(df)

            except Exception as e:
                logger.error(f"Error processing {csv_file.name}: {e}")
                continue

        # Concatenate all dataframes
        consolidated = pd.concat(all_data, ignore_index=True)
        logger.info(f"Total records consolidated: {len(consolidated)}")

        # Standardize columns (add missing columns with None)
        for col in ['notes', 'home_delivery']:
            if col not in consolidated.columns:
                consolidated[col] = None

        # Data quality checks
        self._validate_data(consolidated)

        # Save to CSV
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        consolidated.to_csv(output_path, index=False)
        logger.info(f"Saved consolidated data to {output_path}")

        # Print summary statistics
        self._print_summary(consolidated)

        return consolidated

    def _parse_filename(self, filename: str) -> Dict[str, str]:
        """
        Extract license category and class from filename.

        Args:
            filename: CSV filename (e.g., "AU - Class A Grower.csv")

        Returns:
            Dictionary with 'category' and optional 'class'
        """
        if 'Grower' in filename:
            category = 'Grower'
            if 'Microbusiness' in filename:
                license_class = 'Microbusiness'
            elif 'Class A' in filename:
                license_class = 'A'
            elif 'Class B' in filename:
                license_class = 'B'
            elif 'Class C' in filename:
                license_class = 'C'
            elif 'Excess' in filename:
                license_class = 'Excess'
            else:
                license_class = None
        elif 'Processor' in filename:
            category = 'Processor'
            license_class = None
        elif 'Retailer' in filename:
            category = 'Retailer'
            license_class = None
        elif 'Transporter' in filename:
            category = 'Transporter'
            license_class = None
        else:
            category = 'Unknown'
            license_class = None

        return {'category': category, 'class': license_class}

    def _validate_data(self, df: pd.DataFrame):
        """
        Validate data quality.

        Args:
            df: Consolidated DataFrame
        """
        logger.info("Running data quality checks...")

        # Check for missing addresses
        missing_addresses = df['address'].isna().sum()
        if missing_addresses > 0:
            logger.warning(f"  {missing_addresses} records missing addresses")

        # Check for missing business names
        missing_names = df['business_name'].isna().sum()
        if missing_names > 0:
            logger.warning(f"  {missing_names} records missing business names")

        # Validate address format (should contain 'MI')
        invalid_addresses = df[~df['address'].str.contains('MI', na=False)]
        if len(invalid_addresses) > 0:
            logger.warning(f"  {len(invalid_addresses)} records with addresses missing 'MI'")

        # Check status values
        status_values = df['status'].value_counts()
        logger.info(f"  Status value distribution:")
        for status, count in status_values.items():
            logger.info(f"    {status}: {count}")

    def _print_summary(self, df: pd.DataFrame):
        """
        Print summary statistics.

        Args:
            df: Consolidated DataFrame
        """
        logger.info("\n=== CONSOLIDATION SUMMARY ===")
        logger.info(f"Total Records: {len(df)}")

        logger.info(f"\nBy Program Type:")
        for ptype, count in df['program_type'].value_counts().items():
            logger.info(f"  {ptype}: {count}")

        logger.info(f"\nBy License Category:")
        for category, count in df['license_category'].value_counts().items():
            logger.info(f"  {category}: {count}")

        logger.info(f"\nBy Status:")
        for status, count in df['status'].value_counts().head(10).items():
            logger.info(f"  {status}: {count}")

        logger.info("=" * 30 + "\n")
