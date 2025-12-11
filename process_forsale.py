"""
Extract and geocode FOR SALE retail properties
"""
import pandas as pd
from src.geocoder import GeocodingService

# Extract addresses from the URLs with price and sq ft
forsale_properties = [
    {
        'address': '9017 S Sprinkle Rd, Kalamazoo, MI',
        'url': 'https://www.loopnet.com/Listing/9017-S-Sprinkle-Rd-Kalamazoo-MI/37412011/',
        'price': '$299,000',  # Add actual price here
        'sq_ft': '2005'   # Add actual sq ft here
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
df.to_csv(output_file, index=False)

print(f"\n[SUCCESS] Saved {len(results)} properties to: {output_file}")
print(f"Success rate: {sum(1 for r in results if r['geocode_status'] == 'success')}/{len(results)}")