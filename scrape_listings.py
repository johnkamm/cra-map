"""
Web scraper to extract price and sq ft from FOR SALE listing URLs
"""
import re
from urllib.parse import urlparse

def scrape_listing_info(url):
    """
    Attempt to scrape price and sq ft from a listing URL.

    Returns:
        dict with 'price' and 'sq_ft' keys
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        # Set a user agent to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        domain = urlparse(url).netloc

        price = 'TBD'
        sq_ft = 'TBD'

        # LoopNet specific scraping
        if 'loopnet.com' in domain:
            # Try to find price
            price_elem = soup.find('span', class_=re.compile('.*price.*', re.I))
            if not price_elem:
                price_elem = soup.find(string=re.compile(r'\$[\d,]+'))
            if price_elem:
                price_text = price_elem.get_text() if hasattr(price_elem, 'get_text') else str(price_elem)
                price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', price_text)
                if price_match:
                    price = price_match.group()

            # Try to find sq ft
            sqft_elem = soup.find(string=re.compile(r'[\d,]+\s*(?:SF|sq\.?\s*ft)', re.I))
            if sqft_elem:
                sqft_match = re.search(r'([\d,]+)\s*(?:SF|sq\.?\s*ft)', str(sqft_elem), re.I)
                if sqft_match:
                    sq_ft = sqft_match.group(1)

        # BHHS specific scraping
        elif 'bhhs.com' in domain:
            # Try to find price
            price_elem = soup.find('div', class_=re.compile('.*price.*', re.I))
            if not price_elem:
                price_elem = soup.find(string=re.compile(r'\$[\d,]+'))
            if price_elem:
                price_text = price_elem.get_text() if hasattr(price_elem, 'get_text') else str(price_elem)
                price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', price_text)
                if price_match:
                    price = price_match.group()

            # Try to find sq ft
            sqft_elem = soup.find(string=re.compile(r'[\d,]+\s*(?:SF|sq\.?\s*ft|square feet)', re.I))
            if sqft_elem:
                sqft_match = re.search(r'([\d,]+)\s*(?:SF|sq\.?\s*ft|square feet)', str(sqft_elem), re.I)
                if sqft_match:
                    sq_ft = sqft_match.group(1)

        # AmplifiedRE specific scraping
        elif 'amplifiedre.com' in domain:
            # Try to find price
            price_elem = soup.find(string=re.compile(r'\$[\d,]+'))
            if price_elem:
                price_text = str(price_elem)
                price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', price_text)
                if price_match:
                    price = price_match.group()

            # Try to find sq ft
            sqft_elem = soup.find(string=re.compile(r'[\d,]+\s*(?:SF|sq\.?\s*ft)', re.I))
            if sqft_elem:
                sqft_match = re.search(r'([\d,]+)\s*(?:SF|sq\.?\s*ft)', str(sqft_elem), re.I)
                if sqft_match:
                    sq_ft = sqft_match.group(1)

        return {'price': price, 'sq_ft': sq_ft}

    except Exception as e:
        print(f"  [ERROR] Failed to scrape {url}: {e}")
        return {'price': 'TBD', 'sq_ft': 'TBD'}


if __name__ == '__main__':
    # Test URLs
    test_urls = [
        'https://www.loopnet.com/Listing/9017-S-Sprinkle-Rd-Kalamazoo-MI/37412011/',
        'https://www.bhhs.com/rentals/mi/525-e-kalamazoo-avenue-kalamazoo-49007/pid-389202730',
        'https://www.loopnet.com/Listing/2233-N-Burdick-St-Kalamazoo-MI/37221198/',
        'https://www.amplifiedre.com/property/15-25056372-3301-w-michigan-avenue-battle-creek-MI-49037',
        'https://www.bhhs.com/rentals/mi/625-north-avenue-battle-creek-49017/pid-416593056'
    ]

    print("=== Scraping Listing Information ===\n")

    for url in test_urls:
        print(f"Scraping: {url}")
        result = scrape_listing_info(url)
        print(f"  Price: {result['price']}")
        print(f"  Sq Ft: {result['sq_ft']}")
        print()
