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

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon.se Bestsellers</title>
<style>
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f9f9f9;
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
    border-bottom: 1px solid #ddd;
}

}
.product-info {
    padding: 10px;
}
.product-info h3 {
    font-size: 14px;
    margin: 0 0 5px;
}
.product-info a {
    text-decoration: none;
    color: #333;
}
.product-scroll-container::-webkit-scrollbar {
    display: none;
}
.product-scroll-container {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>
</head>
<body>
<div class="category-header">Electronics</div>
<div class="product-scroll-container">
</div>
<div class="category-header">Books</div>
<div class="product-scroll-container">
</div>
<div class="category-header">Fashion</div>
<div class="product-scroll-container">
</div>
<div class="category-header">Home</div>
<div class="product-scroll-container">
</div>
<div class="category-header">Beauty</div>
<div class="product-scroll-container">
</div>

</body>
</html>


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
        <p>Våra populäraste produkter baserat på försäljning. Uppdateras ofta.</p>
    </header>
""")
        for category, products in products_by_category.items():
            f.write(f"""    <section>
        <h2>{category}</h2>
        <div class="container">
""")
            for p in products:
                img_html = f"<img src='{p['img']}' alt='{p['title']}'>" if p['img'] else ""
                f.write(f"""            <div class="product">
                <a href="{build_affiliate_link(p['asin'])}" target="_blank">
                    {img_html}
                    <h3>{p['title']}</h3>
                </a>
                <div class="price"></div>
            </div>
""")
        f.write("        </div>\n")
        f.write("    </section>\n")
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
            if len(products) >= 12:
                break
            time.sleep(1)
        products_by_category[category] = products
    generate_html(products_by_category, 'index.html')
    print('Wrote index.html with top 12 products per category.')






