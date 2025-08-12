
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

def get_top_asins(url, limit=15):
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
        margin: 0;
        background-color: #ffffff;
        color: #000000;
    }
    header {
        background-color: #000000;
        color: #ffffff;
        padding: 20px;
        text-align: center;
        position: sticky;
        top: 0;
        z-index: 1000;
    }
    header h1 {
        margin: 0;
        font-size: 2em;
    }
    header p {
        margin: 5px 0 10px;
        font-size: 1.1em;
    }
    nav {
        margin-top: 10px;
    }
    nav a {
        margin: 0 10px;
        color: #ffffff;
        text-decoration: none;
        font-weight: bold;
    }
    nav a.active {
        background-color: #ffffff;
        color: #000000;
        padding: 5px 10px;
        border-radius: 5px;
    }
    section {
        padding: 20px;
        max-width: 1200px;
        margin: auto;
        scroll-margin-top: 120px;
    }
    section h2 {
        font-size: 2em;
        font-weight: bold;
        margin-top: 40px;
        margin-bottom: 20px;
        background-color: #D3D3D3;
        border-bottom: 2px solid #000;
        padding-bottom: 10px;
        text-align: center;
    }
    .container {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
    }
    .product {
        background-color: #f9f9f9;
        border: 1px solid #000000;
        border-radius: 10px;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.1);
        margin: 10px;
        padding: 15px;
        width: 200px;
        text-align: center;
    }
    .product img {
        max-width: 100%;
        height: auto;
        margin-bottom: 10px;
    }
    .product h3 {
        font-size: 1em;
        margin: 0.5em 0;
        color: #000000;
    }
    .product a {
        text-decoration: none;
        color: #000000;
    }
    .price {
        font-size: 1.1em;
        font-weight: bold;
        color: #000000;
    }
    @media (max-width: 600px) {
        .product {
            width: 90%;
        }
        section {
            padding: 10px;
        }
    }
    """

    js_script = """
    <script>
    window.addEventListener('scroll', function() {
        const sections = document.querySelectorAll('section');
        const navLinks = document.querySelectorAll('nav a');
        let currentId = '';
        sections.forEach(section => {
            const rect = section.getBoundingClientRect();
            if (rect.top <= 120 && rect.bottom >= 120) {
                currentId = section.id;
            }
        });
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === '#' + currentId) {
                link.classList.add('active');
            }
        });
    });
    </script>
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
        <p>Våra populäraste produkter baserat på försäljning. Scrolla ner för fler kategorier.</p>
        <nav>
""")
        for category in products_by_category:
            section_id = re.sub(r'[^a-zA-Z0-9]', '-', category.lower())
            f.write(f'            <a href="#{section_id}">{category}</a>
')
        f.write("""        </nav>
    </header>
""")
        for category, products in products_by_category.items():
            section_id = re.sub(r'[^a-zA-Z0-9]', '-', category.lower())
            f.write(f"""    <section id="{section_id}">
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
            f.write("        </div>
    </section>
")
        f.write(f"{js_script}</body>
</html>")

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
