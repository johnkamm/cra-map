"""
Create a diverse sample of records for testing (includes all license types)
"""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.geocoder import GeocodingService

# Load consolidated data
df = pd.read_csv('data/processed/consolidated_licenses.csv')

# Sample 10 records from each license category
sample_dfs = []
for category in df['license_category'].unique():
    category_df = df[df['license_category'] == category]
    sample_size = min(10, len(category_df))
    sample_dfs.append(category_df.head(sample_size))

df_sample = pd.concat(sample_dfs, ignore_index=True)
print(f"Created diverse sample with {len(df_sample)} records")
print("\nSample distribution:")
print(df_sample.groupby(['license_category', 'program_type']).size())

# Geocode the sample
geocoder = GeocodingService()
df_geocoded = geocoder.geocode_dataframe(df_sample, test_mode=False)

# Save
df_geocoded.to_csv('data/processed/geocoded_licenses.csv', index=False)
print("\n[SUCCESS] Saved diverse sample to geocoded_licenses.csv")
print("Now run: python generate_map.py")
