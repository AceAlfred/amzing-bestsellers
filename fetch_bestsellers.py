import os
import re
import time
import requests
from bs4 import BeautifulSoup

# Define categories and their Amazon.se bestseller URLs
CATEGORIES = {
    "Beauty & Personal Care": "https://www.amazon.se/gp/bestsellers/beauty",
    "Home & Kitchen": "https://www.amazon.se/gp/bestsellers/home",
    "Clothing, Shoes & Jewelry": "https://www.amazon.se/gp/bestsellers/fashion",
    "Electronics": "https://www.amazon.se/gp/bestsellers/electronics",
    "Toys & Games": "https://www.amazon.se/gp/bestsellers/toys",
    "Books": "https://www.amazon.se/gp/bestsellers/books",
    "Sports & Outdoors": "https://www.amazon.se/gp/bestsellers/sports",
    "Health & Household": "https://www.amazon.se/gp/bestsellers/hpc",
    "Tools & Home Improvement": "https://www.amazon.se/gp/bestsellers/hi",
    "Pet Supplies": "https://www.amazon.se/gp/bestsellers/pet-supplies"
}

ASSOCIATE_TAG = 'amzing2025-21'#os.getenv('AMZ_ASSOC_TAG') or os.getenv('PA_TAG', '')
PAAPI_ENABLED = os.getenv('PAAPI_ENABLED', 'false').lower() in ('1','true')
PA_ACCESS_KEY = os.getenv('PA_ACCESS_KEY','')
PA_SECRET_KEY = os.getenv('PA_SECRET_KEY','')
PA_PARTNER_TAG = ASSOCIATE_TAG
REGION = 'eu-west-1'  # Amazon PA-API region. For Amazon.se use "eu-west-1" endpoints.

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

session = requests.Session()
session.headers.update(HEADERS)

def get_top_asins(url, limit=10):
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
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f8f9fa;
            color: #333;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
        }
        h2 {
            margin-top: 40px;
            color: #0073bb;
        }
        .product {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 15px;
            margin: 15px;
            background-color: white;
            text-align: center;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.1);
            width: 250px;
        }
        .product img {
            max-width: 200px;
            height: auto;
            cursor: pointer;
        }
        .product a {
            text-decoration: none;
            color: #0073bb;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
        }
        .price {
            font-size: 18px;
            font-weight: bold;
            margin-top: 10px;
            color: #b12704;
        }
    """

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amazon Top 10 per Category - Sverige</title>
    <style>{css_styles}</style>
</head>
<body>
    <h1>Amazon Top 10 per Category - Sverige</h1>
""")
        for category, products in products_by_category.items():
            f.write(f"<h2>{category}</h2>\n<div class='container'>\n")
            for p in products:
                img_html = f"<img src='{p['img']}' alt='{p['title']}'>" if p['img'] else ""
                f.write(f"""<div class="product">
            <a href="{build_affiliate_link(p['asin'])}" target="_blank">
                {img_html}
            </a>
            <a href="{build_affiliate_link(p['asin'])}" target="_blank">
                <h3>{p['title']}</h3>
            </a>
            <div class="price"></div>
        </div>
""")
            f.write("</div>\n")
        f.write("</body>\n</html>")

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
            if len(products) >= 10:
                break
            time.sleep(1)
        products_by_category[category] = products
    generate_html(products_by_category, 'index.html')
    print('Wrote index.html with top 10 products per category.')
