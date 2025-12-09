import pandas as pd

df = pd.read_csv('data/processed/geocoded_licenses.csv')
failed = df[df['geocode_status'] != 'success']

print('\n=== FAILED ADDRESSES ===\n')
for idx, row in failed.iterrows():
    print(f'{idx+1}. {row["business_name"]}')
    print(f'   Address: {row["address"]}')
    print(f'   Status: {row["geocode_status"]}\n')
