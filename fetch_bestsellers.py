# Requires: requests, beautifulsoup4
import os
import re
import time
import requests
from bs4 import BeautifulSoup

AMAZON_BESTSELLERS_URL = 'https://www.amazon.se/gp/bestsellers'
ASSOCIATE_TAG = os.getenv('AMZ_ASSOC_TAG') or os.getenv('PA_TAG', '')
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

def get_top_asins(limit=10):
    """Scrape Amazon.se Bestsellers page and pull first unique ASINs."""
    r = session.get(AMAZON_BESTSELLERS_URL, timeout=20)
    r.raise_for_status()
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
    """Get title and image from product page (lightweight)."""
    url = f'https://www.amazon.se/dp/{asin}'
    r = session.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    title_tag = soup.find(id='productTitle') or soup.find('span', class_='a-size-large')
    title = title_tag.get_text(strip=True) if title_tag else asin
    img = None
    img_tag = soup.find(id='landingImage') or soup.select_one('#imgTagWrapperId img')
    if img_tag and img_tag.get('src'):
        img = img_tag['src']
    return {'asin': asin, 'title': title, 'img': img, 'url': url}

def build_affiliate_link(asin):
    return f'https://www.amazon.se/dp/{asin}/?tag={ASSOCIATE_TAG}'

def generate_html(products, out_path='index.html'):
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
    <title>Amazon Top 10 - Sverige</title>
    <style>{css_styles}</style>
</head>
<body>
    <h1>Amazon Top 10 - Sverige</h1>
    <div class="container">
""")
        for p in products:
            if not p.get('img'):
                p['img'] = ''
            f.write(f"""
        <div class="product">
            <a href="{build_affiliate_link(p['asin'])}" target="_blank">
                <img src="{p['img']}" alt="{p['title']}">
            </a>
            <a href="{build_affiliate_link(p['asin'])}" target="_blank">
                <h2>{p['title']}</h2>
            </a>
            <div class="price"></div>
        </div>
""")
        f.write("""
    </div>
</body>
</html>""")

if __name__ == '__main__':
    asins = get_top_asins(10)
    products = []
    for asin in asins:
        try:
            info = fetch_product_basic(asin)
        except Exception as e:
            print('Failed to fetch', asin, e)
            info = {'asin': asin, 'title': asin, 'img': None, 'url': f'https://www.amazon.se/dp/{asin}'}
        products.append(info)
        time.sleep(1)
    generate_html(products, 'index.html')
    print('Wrote index.html with', len(products), 'products')



