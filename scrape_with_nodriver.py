"""
Web scraper using nodriver to extract price and sq ft from FOR SALE listings
"""
import asyncio
import re
import nodriver as uc

async def scrape_listing(url):
    """Scrape a single listing URL for price and sq ft"""
    browser = None
    try:
        browser = await uc.start(headless=True)
        page = await browser.get(url)

        # Wait for page to load
        await asyncio.sleep(5)

        # Get page text content
        html = await page.get_content()

        # Extract price using regex
        price = 'TBD'
        price_patterns = [
            r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:/mo|/month|per month))?',
            r'Price[:\s]*\$[\d,]+',
            r'Asking[:\s]*\$[\d,]+',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                price = match.group()
                # Clean up the price
                price = re.sub(r'Price[:\s]*', '', price, flags=re.I)
                price = re.sub(r'Asking[:\s]*', '', price, flags=re.I)
                break

        # Extract sq ft using regex
        sq_ft = 'TBD'
        sqft_patterns = [
            r'([\d,]+)\s*(?:SF|sq\.?\s*ft|square feet)',
            r'([\d,]+)\s*SF',
            r'Building Size[:\s]*([\d,]+)',
        ]
        for pattern in sqft_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                sq_ft = match.group(1)
                break

        return {'price': price, 'sq_ft': sq_ft}

    except Exception as e:
        print(f"  [ERROR] {e}")
        return {'price': 'TBD', 'sq_ft': 'TBD'}
    finally:
        if browser:
            browser.stop()

async def main():
    """Scrape all listings"""
    urls = [
        'https://www.loopnet.com/Listing/9017-S-Sprinkle-Rd-Kalamazoo-MI/37412011/',
        'https://www.bhhs.com/rentals/mi/525-e-kalamazoo-avenue-kalamazoo-49007/pid-389202730',
        'https://www.loopnet.com/Listing/2233-N-Burdick-St-Kalamazoo-MI/37221198/',
        'https://www.amplifiedre.com/property/15-25056372-3301-w-michigan-avenue-battle-creek-MI-49037',
        'https://www.bhhs.com/rentals/mi/625-north-avenue-battle-creek-49017/pid-416593056'
    ]

    print("=== Scraping Listings with nodriver ===\n")

    results = []
    for url in urls:
        print(f"Scraping: {url}")
        result = await scrape_listing(url)
        print(f"  Price: {result['price']}")
        print(f"  Sq Ft: {result['sq_ft']}\n")
        results.append({'url': url, **result})

    return results

if __name__ == '__main__':
    results = asyncio.run(main())

    print("\n=== Summary ===")
    for r in results:
        print(f"{r['url']}")
        print(f"  Price: {r['price']}, Sq Ft: {r['sq_ft']}")
