import os
import re
import time
import requests
from bs4 import BeautifulSoup

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

session = requests.Session()
session.headers.update(HEADERS)

def get_top_asins(url, limit=12):
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch category page: {url}", e)
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    asins = []
    for tag in soup.select('[data-asin]'):
        asin = tag.get('data-asin')
        if asin and asin not in asins:
            asins.append(asin)
        if len(asins) >= limit:
            break

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

def fetch_product_basic(asin):
    url = f'https://www.amazon.se/dp/{asin}'
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch product page: {url}", e)
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    title_tag = soup.find(id='productTitle') or soup.find('span', class_='a-size-large')
    title = title_tag.get_text(strip=True) if title_tag else asin
    if 'gift card' in title.lower() or 'presentkort' in title.lower():
        return None
    img = None
    img_tag = soup.find(id='landingImage') or soup.select_one('#imgTagWrapperId img')
    if img_tag and img_tag.get('src'):
        img = img_tag['src']
    return {'asin': asin, 'title': title, 'img': img, 'url': url}

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
}

.product-card img {
    max-width: 90%;
    max-height: 90%;
    object-fit: contain;
    transition: transform 0.3s ease;
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
        <h1>🏆Bästsäljare på Amazon</h1>
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
                img_html = f'<img src="{p["img"]}" alt="{p["title"]}" loading="lazy">' if p['img'] else '<div style="color: #bdc3c7; font-size: 3rem;">📦</div>'
                f.write(f"""            <div class="product-card">
                <a href="{build_affiliate_link(p['asin'])}" target="_blank" rel="noopener">
                    <div class="image-container">
                        {img_html}
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
    products_by_category = {}
    for category, url in CATEGORIES.items():
        print(f"Processing category: {category}")
        asins = get_top_asins(url, limit=15)
        products = []
        for asin in asins:
            info = fetch_product_basic(asin)
            if info:
                products.append(info)
            if len(products) >= 12:
                break
            time.sleep(1)
        products_by_category[category] = products
        
    generate_html(products_by_category, 'index.html')
    print('Wrote index.html with top 12 products per category.')
