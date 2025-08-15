import os
import re
import time
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from threading import Lock
import json
from datetime import datetime, timedelta

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

# Create session pool for concurrent requests
session_pool = []
session_lock = Lock()
CACHE_FILE = 'products_cache.json'
CACHE_DURATION_HOURS = 2

def get_session():
    """Get a session from the pool or create a new one"""
    with session_lock:
        if session_pool:
            return session_pool.pop()
    
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def return_session(session):
    """Return session to pool for reuse"""
    with session_lock:
        if len(session_pool) < 5:  # Limit pool size
            session_pool.append(session)

def load_cache():
    """Load cached products if they're still fresh"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data['timestamp'])
                if datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS):
                    print(f"Using cached data from {cache_time}")
                    return cache_data['products']
    except Exception as e:
        print(f"Cache load failed: {e}")
    return None

def save_cache(products_data):
    """Save products to cache"""
    try:
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'products': products_data
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Cache save failed: {e}")

def get_top_asins(url, limit=12):
    """Fetch top ASINs from category page with session pooling"""
    session = get_session()
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch category page: {url}", e)
        return []
    finally:
        return_session(session)

    soup = BeautifulSoup(r.text, 'html.parser')
    asins = []
    
    # First, try to get ASINs from data-asin attributes
    for tag in soup.select('[data-asin]'):
        asin = tag.get('data-asin')
        if asin and len(asin) == 10 and asin.isalnum() and asin not in asins:
            asins.append(asin)
        if len(asins) >= limit:
            break

    # If not enough, extract from URLs
    if len(asins) < limit:
        asin_pattern = re.compile(r'/dp/([A-Z0-9]{10})')
        for a in soup.find_all('a', href=True):
            match = asin_pattern.search(a['href'])
            if match:
                asin = match.group(1)
                if asin not in asins:
                    asins.append(asin)
                if len(asins) >= limit:
                    break

    return asins[:limit]

def fetch_product_basic(asin):
    """Fetch basic product info with session pooling and better error handling"""
    session = get_session()
    url = f'https://www.amazon.se/dp/{asin}'
    
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch product {asin}: {e}")
        return None
    finally:
        return_session(session)

    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Get title with multiple fallbacks
    title_selectors = [
        '#productTitle',
        'span.a-size-large',
        'h1.a-size-large',
        '.product-title'
    ]
    
    title = asin  # Default fallback
    for selector in title_selectors:
        title_tag = soup.select_one(selector)
        if title_tag:
            title = title_tag.get_text(strip=True)
            break
    
    # Skip gift cards
    if any(term in title.lower() for term in ['gift card', 'presentkort', 'gavekort']):
        return None
    
    # Get image with multiple fallbacks and fix URL
    img_selectors = [
        '#landingImage',
        '#imgTagWrapperId img',
        '.a-dynamic-image',
        'img.a-dynamic-image',
        '[data-old-hires]',
        '[data-a-dynamic-image]'
    ]
    
    img = None
    for selector in img_selectors:
        img_tag = soup.select_one(selector)
        if img_tag:
            # Try different attributes for image URL
            img_url = (img_tag.get('data-old-hires') or 
                      img_tag.get('data-a-dynamic-image') or 
                      img_tag.get('src') or 
                      img_tag.get('data-src'))
            
            if img_url:
                # Clean up the image URL for better loading
                if img_url.startswith('data:'):
                    continue  # Skip base64 images
                
                # Extract JSON data if present
                if img_url.startswith('{'):
                    try:
                        import json
                        img_data = json.loads(img_url)
                        if isinstance(img_data, dict):
                            # Get the largest image
                            img_url = max(img_data.keys(), key=lambda x: int(x.split(',')[0]) if ',' in x else 0)
                    except:
                        continue
                
                # Ensure HTTPS and proper format
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    img_url = 'https://images-na.ssl-images-amazon.com' + img_url
                
                # Replace size parameters for better quality and loading
                if 'images-amazon.com' in img_url:
                    # Remove size restrictions and add proper size
                    img_url = re.sub(r'\._[A-Z0-9,_]+_\.', '._AC_SL300_.', img_url)
                    img = img_url
                    break
    
    return {
        'asin': asin,
        'title': title[:100],  # Limit title length
        'img': img,
        'url': url
    }

def process_category(category_data):
    """Process a single category - for parallel execution"""
    category, url = category_data
    print(f"Processing category: {category}")
    
    asins = get_top_asins(url, limit=15)
    if not asins:
        print(f"No ASINs found for {category}")
        return category, []
    
    products = []
    
    # Use ThreadPoolExecutor for concurrent product fetching
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_asin = {executor.submit(fetch_product_basic, asin): asin for asin in asins}
        
        for future in concurrent.futures.as_completed(future_to_asin):
            try:
                product_info = future.result(timeout=20)
                if product_info:
                    products.append(product_info)
                if len(products) >= 12:
                    break
            except Exception as e:
                asin = future_to_asin[future]
                print(f"Product fetch failed for {asin}: {e}")
    
    print(f"Found {len(products)} products for {category}")
    return category, products

def build_affiliate_link(asin):
    return f'https://www.amazon.se/dp/{asin}/?tag={ASSOCIATE_TAG}'

def generate_html(products_by_category, out_path='index.html'):
    css_styles = """
/* Reset and base styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px 0;
}

/* Header styles */
header {
    text-align: center;
    padding: 40px 20px;
    background: rgba(255, 255, 255, 0.95);
    margin: 0 20px 30px;
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

header h1 {
    font-size: 2.5rem;
    color: #2c3e50;
    margin-bottom: 10px;
    font-weight: 700;
}

header p {
    font-size: 1.1rem;
    color: #7f8c8d;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.6;
}

/* Category section */
.category-section {
    margin: 0 20px 40px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.category-header {
    background: linear-gradient(135deg, #3498db, #2980b9);
    color: white;
    padding: 20px 25px;
    font-size: 1.4rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 3px solid #2c3e50;
}

/* Product scroll container */
.product-scroll-container {
    display: flex;
    overflow-x: auto;
    gap: 20px;
    padding: 25px;
    scroll-snap-type: x mandatory;
    scrollbar-width: thin;
    scrollbar-color: #bdc3c7 transparent;
}

.product-scroll-container::-webkit-scrollbar {
    height: 8px;
}

.product-scroll-container::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 10px;
}

.product-scroll-container::-webkit-scrollbar-thumb {
    background: linear-gradient(135deg, #3498db, #2980b9);
    border-radius: 10px;
}

.product-scroll-container::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(135deg, #2980b9, #3498db);
}

/* Product card styles */
.product-card {
    flex: 0 0 auto;
    width: 220px;
    background: white;
    border-radius: 15px;
    overflow: hidden;
    scroll-snap-align: start;
    transition: all 0.3s ease;
    border: 2px solid transparent;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.product-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.15);
    border-color: #3498db;
}

/* Image container */
.image-container {
    width: 100%;
    height: 200px;
    background: #f8f9fa;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 2px solid #ecf0f1;
    overflow: hidden;
    position: relative;
}

.product-card img {
    max-width: 90%;
    max-height: 90%;
    object-fit: contain;
    transition: transform 0.3s ease;
    background: white;
    border-radius: 4px;
    padding: 5px;
}

.product-card img[src=""], 
.product-card img:not([src]) {
    display: none;
}

.product-card .no-image {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 90%;
    height: 90%;
    background: linear-gradient(135deg, #f0f0f0, #e0e0e0);
    border-radius: 8px;
    color: #999;
    font-size: 2.5rem;
    border: 2px dashed #ccc;
}

.product-card:hover img {
    transform: scale(1.05);
}

/* Product info */
.product-info {
    padding: 20px;
    border-top: 1px solid #ecf0f1;
}

.product-info h3 {
    font-size: 0.95rem;
    line-height: 1.4;
    color: #2c3e50;
    margin: 0;
    font-weight: 600;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
    min-height: 60px;
}

.product-info a {
    text-decoration: none;
    color: inherit;
    display: block;
}

.product-info a:hover h3 {
    color: #3498db;
}

/* Price placeholder */
.price {
    margin-top: 10px;
    padding: 8px;
    background: linear-gradient(135deg, #27ae60, #2ecc71);
    color: white;
    text-align: center;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.9rem;
}

.price:empty::after {
    content: "Se pris på Amazon";
}

/* Responsive design */
@media (max-width: 768px) {
    body {
        padding: 10px 0;
    }
    
    header {
        margin: 0 10px 20px;
        padding: 30px 15px;
    }
    
    header h1 {
        font-size: 2rem;
    }
    
    .category-section {
        margin: 0 10px 30px;
    }
    
    .product-card {
        width: 180px;
    }
    
    .product-scroll-container {
        padding: 20px 15px;
        gap: 15px;
    }
}

@media (max-width: 480px) {
    .product-card {
        width: 160px;
    }
    
    .image-container {
        height: 160px;
    }
    
    .product-info {
        padding: 15px;
    }
    
    .product-info h3 {
        font-size: 0.85rem;
        min-height: 50px;
    }
}
"""

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bästsäljare på Amazon Sverige</title>
    <meta name="description" content="Upptäck de populäraste produkterna på Amazon Sverige. Våra bästsäljare uppdateras dagligen.">
    <style>{css_styles}</style>
</head>
<body>
    <header>
        <h1>🏆 Bästsäljare på Amazon</h1>
        <p>Upptäck våra populäraste produkter baserat på försäljning. Uppdateras dagligen för att ge dig de hetaste trenderna.</p>
    </header>
""")
        
        for category, products in products_by_category.items():
            if not products:  # Skip empty categories
                continue
                
            f.write(f"""    <section class="category-section">
        <div class="category-header">{category}</div>
        <div class="product-scroll-container">
""")
            for p in products:
                # Better image handling with fallback
                if p['img']:
                    img_html = f'<img src="{p["img"]}" alt="{p["title"]}" loading="lazy" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';">'
                    fallback_html = f'<div class="no-image" style="display: none;">📦</div>'
                else:
                    img_html = ''
                    fallback_html = f'<div class="no-image">📦</div>'
                    
                f.write(f"""            <div class="product-card">
                <a href="{build_affiliate_link(p['asin'])}" target="_blank" rel="noopener">
                    <div class="image-container">
                        {img_html}
                        {fallback_html}
                    </div>
                    <div class="product-info">
                        <h3>{p['title']}</h3>
                        <div class="price"></div>
                    </div>
                </a>
            </div>
""")
            f.write("""        </div>
    </section>
""")
        
        f.write("""</body>
</html>""")

if __name__ == '__main__':
    start_time = time.time()
    
    # Try to load from cache first
    cached_data = load_cache()
    if cached_data:
        products_by_category = cached_data
        print("Using cached data - skipping web scraping")
    else:
        print("No valid cache found - starting fresh scraping")
        products_by_category = {}
        
        # Process categories in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_category = {
                executor.submit(process_category, (category, url)): category 
                for category, url in CATEGORIES.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_category):
                try:
                    category, products = future.result(timeout=60)
                    products_by_category[category] = products
                except Exception as e:
                    category = future_to_category[future]
                    print(f"Category processing failed for {category}: {e}")
                    products_by_category[category] = []
        
        # Save to cache
        save_cache(products_by_category)
    
    # Generate HTML
    generate_html(products_by_category, 'index.html')
    
    elapsed_time = time.time() - start_time
    total_products = sum(len(products) for products in products_by_category.values())
    
    print(f'\n✅ Completed in {elapsed_time:.1f} seconds')
    print(f'📦 Generated index.html with {total_products} products across {len(products_by_category)} categories')
    print(f'⚡ Average: {total_products/elapsed_time:.1f} products/second')
