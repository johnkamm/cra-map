"""
Extract and geocode FOR SALE retail properties
"""
import pandas as pd
from src.geocoder import GeocodingService

# Original 5 properties with sq_ft data
forsale_properties = [
    {
        'address': '9017 S Sprinkle Rd, Kalamazoo, MI',
        'url': 'https://www.loopnet.com/Listing/9017-S-Sprinkle-Rd-Kalamazoo-MI/37412011/',
        'price': '$299,000',
        'sq_ft': '2005'
    },
    {
        'address': '525 E Kalamazoo Avenue, Kalamazoo, MI 49007',
        'url': 'https://www.bhhs.com/rentals/mi/525-e-kalamazoo-avenue-kalamazoo-49007/pid-389202730',
        'price': '$399,999',
        'sq_ft': '2674'
    },
    {
        'address': '2233 N Burdick St, Kalamazoo, MI',
        'url': 'https://www.loopnet.com/Listing/2233-N-Burdick-St-Kalamazoo-MI/37221198/',
        'price': '$585,000',
        'sq_ft': '4072'
    },
    {
        'address': '3301 W Michigan Avenue, Battle Creek, MI 49037',
        'url': 'https://www.amplifiedre.com/property/15-25056372-3301-w-michigan-avenue-battle-creek-MI-49037',
        'price': '$475,000',
        'sq_ft': '2765'
    },
    {
        'address': '625 North Avenue, Battle Creek, MI 49017',
        'url': 'https://www.bhhs.com/rentals/mi/625-north-avenue-battle-creek-49017/pid-416593056',
        'price': '$500,000',
        'sq_ft': '2100'
    }
]

# Read additional properties from CSV
df = pd.read_csv('ForSale-25-12-16.csv')

# Add CSV properties to the list
for _, row in df.iterrows():
    # Combine Address and City for full address
    full_address = f"{row['Address']}, {row['City']}, MI"

    forsale_properties.append({
        'address': full_address,
        'url': row['Listing URL'],
        'price': row['Price'],
        'sq_ft': None  # Not available in CSV
    })

print("=== Geocoding FOR SALE Properties ===\n")

geocoder = GeocodingService()
results = []

for prop in forsale_properties:
    print(f"Geocoding: {prop['address']}")
    result = geocoder.geocode_address(prop['address'])

    if result['status'] == 'success':
        print(f"  [OK] Success: {result['latitude']}, {result['longitude']}")
        results.append({
            'address': prop['address'],
            'url': prop['url'],
            'price': prop['price'],
            'sq_ft': prop['sq_ft'],
            'latitude': result['latitude'],
            'longitude': result['longitude'],
            'geocode_status': 'success',
            'geocode_source': result.get('source', 'unknown')
        })
    else:
        print(f"  [FAIL] Failed: {result['status']}")
        results.append({
            'address': prop['address'],
            'url': prop['url'],
            'price': prop['price'],
            'sq_ft': prop['sq_ft'],
            'latitude': None,
            'longitude': None,
            'geocode_status': result['status'],
            'geocode_source': None
        })

# Save to CSV
df = pd.DataFrame(results)
output_file = 'data/processed/forsale_properties.csv'
# Replace NaN/None with empty strings in the CSV
df.to_csv(output_file, index=False, na_rep='')

print(f"\n[SUCCESS] Saved {len(results)} properties to: {output_file}")
print(f"Success rate: {sum(1 for r in results if r['geocode_status'] == 'success')}/{len(results)}")