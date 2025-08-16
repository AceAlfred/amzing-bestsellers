import os
import re
import time
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import functools

# Define categories and their Amazon.se bestseller URLs
CATEGORIES = {
    "Beauty & Personal Care": "https://www.amazon.se/gp/bestsellers/beauty",
    "Home & Kitchen": "https://www.amazon.se/gp/bestsellers/kitchen",
    "Clothing, Shoes & Jewelry": "https://www.amazon.se/gp/bestsellers/fashion",
    "Electronics": "https://www.amazon.se/gp/bestsellers/electronics",
    "Toys & Games": "https://www.amazon.se/gp/bestsellers/toys",
    "Books": "https://www.amazon.se/gp/bestsellers/books",
    "Sports & Outdoors": "https://www.amazon.se/gp/bestsellers/sports",
    "Health & Household": "https://www.amazon.se/gp/bestsellers/health",
    "Tools & Home Improvement": "https://www.amazon.se/gp/bestsellers/industrial",
    "Pet Supplies": "https://www.amazon.se/gp/bestsellers/pet-supplies"
}

ASSOCIATE_TAG = 'amzing2025-21'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

# Async HTTP session
async def create_session():
    timeout = aiohttp.ClientTimeout(total=20)
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=5)  # Connection pooling
    return aiohttp.ClientSession(
        headers=HEADERS, 
        timeout=timeout, 
        connector=connector
    )

async def get_top_asins(session, url, limit=12):
    """Async version of get_top_asins"""
    try:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Failed to fetch category page: {url}, status: {response.status}")
                return []
            text = await response.text()
    except Exception as e:
        print(f"Failed to fetch category page: {url}", e)
        return []

    # Use ThreadPoolExecutor for CPU-bound parsing
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        asins = await loop.run_in_executor(executor, parse_asins_from_html, text, limit)
    
    return asins

def parse_asins_from_html(html_text, limit):
    """Parse ASINs from HTML (CPU-bound, runs in thread pool)"""
    soup = BeautifulSoup(html_text, 'html.parser')
    asins = []
    
    # First method: look for data-asin attributes
    for tag in soup.select('[data-asin]'):
        asin = tag.get('data-asin')
        if asin and asin not in asins:
            asins.append(asin)
        if len(asins) >= limit:
            break

    # Second method: regex search in hrefs
    if len(asins) < limit:
        for a in soup.find_all('a', href=True):
            m = re.search(r'/dp/([A-Z0-9]{10})', a['href'])
            if m:
                asin = m.group(1)
                if asin not in asins:
                    asins.append(asin)
                if len(asins) >= limit:
                    break

    return asins[:limit]

async def fetch_product_basic(session, asin):
    """Async version of fetch_product_basic"""
    url = f'https://www.amazon.se/dp/{asin}'
    try:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Failed to fetch product page: {url}, status: {response.status}")
                return None
            text = await response.text()
    except Exception as e:
        print(f"Failed to fetch product page: {url}", e)
        return None

    # Use ThreadPoolExecutor for CPU-bound parsing
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        product_data = await loop.run_in_executor(
            executor, parse_product_from_html, text, asin, url
        )
    
    return product_data

def parse_product_from_html(html_text, asin, url):
    """Parse product data from HTML (CPU-bound, runs in thread pool)"""
    soup = BeautifulSoup(html_text, 'html.parser')
    
    title_tag = soup.find(id='productTitle') or soup.find('span', class_='a-size-large')
    title = title_tag.get_text(strip=True) if title_tag else asin
    
    # Skip gift cards
    if 'gift card' in title.lower() or 'presentkort' in title.lower():
        return None
    
    img = None
    img_tag = soup.find(id='landingImage') or soup.select_one('#imgTagWrapperId img')
    if img_tag and img_tag.get('src'):
        img = img_tag['src']
    
    return {'asin': asin, 'title': title, 'img': img, 'url': url}

async def process_category(session, category, url, limit=12):
    """Process a single category asynchronously"""
    print(f"Processing category: {category}")
    asins = await get_top_asins(session, url, limit=15)
    
    if not asins:
        return category, []
    
    # Process products concurrently with controlled concurrency
    semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
    
    async def fetch_with_semaphore(asin):
        async with semaphore:
            return await fetch_product_basic(session, asin)
    
    # Fetch all products concurrently
    tasks = [fetch_with_semaphore(asin) for asin in asins]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter successful results and limit to 12
    products = []
    for result in results:
        if isinstance(result, dict) and result is not None:
            products.append(result)
        if len(products) >= limit:
            break
    
    return category, products

def build_affiliate_link(asin):
    return f'https://www.amazon.se/dp/{asin}/?tag={ASSOCIATE_TAG}'

def generate_html(products_by_category, out_path='index.html'):
    """Generate HTML file (fixed the malformed HTML structure)"""
    css_styles = """
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f9f9f9;
}
header {
    background-color: #232f3e;
    color: white;
    text-align: center;
    padding: 20px;
}
.category-header {
    background-color: #e0e0e0;
    padding: 10px;
    font-size: 18px;
    font-weight: bold;
}
.product-scroll-container {
    display: flex;
    overflow-x: auto;
    gap: 10px;
    padding: 10px;
    scroll-snap-type: x mandatory;
}
.product-card {
    flex: 0 0 auto;
    width: 45vw;
    max-width: 180px;
    border: 1px solid #ccc;
    border-radius: 8px;
    scroll-snap-align: start;
    background: #fff;
}
.product-card img {
    display: block;
    margin: auto;
    width: 100%;
    height: 150px;
    object-fit: contain;
    border-bottom: 1px solid #ddd;
}
.product-info {
    padding: 10px;
}
.product-info h3 {
    font-size: 14px;
    margin: 0 0 5px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}
.product-info a {
    text-decoration: none;
    color: #333;
}
.product-info a:hover {
    color: #0066c0;
}
.product-scroll-container::-webkit-scrollbar {
    display: none;
}
.product-scroll-container {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
"""

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bästsäljare på Amazon</title>
    <style>{css_styles}</style>
</head>
<body>
    <header>
        <h1>Bästsäljare på Amazon</h1>
        <p>Våra populäraste produkter baserat på försäljning. Uppdateras dagligen.</p>
    </header>
""")
        
        for category, products in products_by_category.items():
            f.write(f"""    <section>
        <div class="category-header">{category}</div>
        <div class="product-scroll-container">
""")
            for p in products:
                img_html = f"<img src='{p['img']}' alt='{p['title']}'>" if p['img'] else ""
                f.write(f"""            <div class="product-card">
                <a href="{build_affiliate_link(p['asin'])}" target="_blank">
                    {img_html}
                    <div class="product-info">
                        <h3>{p['title']}</h3>
                    </div>
                </a>
            </div>
""")
            f.write("        </div>\n    </section>\n")
        
        f.write("</body>\n</html>")

async def main():
    """Main async function"""
    session = await create_session()
    
    try:
        # Process all categories concurrently
        tasks = [
            process_category(session, category, url) 
            for category, url in CATEGORIES.items()
        ]
        
        # Execute all category processing concurrently
        results = await asyncio.gather(*tasks)
        
        # Convert results to dictionary
        products_by_category = dict(results)
        
        # Generate HTML
        generate_html(products_by_category, 'index.html')
        print('Wrote index.html with top 12 products per category.')
        
    finally:
        await session.close()

if __name__ == '__main__':
    # Install required packages if not already installed:
    # pip install aiohttp beautifulsoup4
    
    start_time = time.time()
    asyncio.run(main())
    end_time = time.time()
    print(f"Execution completed in {end_time - start_time:.2f} seconds")
