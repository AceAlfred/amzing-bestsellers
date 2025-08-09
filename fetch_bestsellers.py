----- fetch_bestsellers.py -----
# Requires: requests, beautifulsoup4
# Optional: amazon-paapi (official) or custom signed requests

import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup

AMAZON_BESTSELLERS_URL = 'https://www.amazon.se/gp/bestsellers'
ASSOCIATE_TAG = os.getenv('AMZ_ASSOC_TAG', 'YOURTAG-21')
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
    # On bestsellers pages ASIN often appears in data-asin attributes or links like /dp/ASIN
    for tag in soup.select('[data-asin]'):
        asin = tag.get('data-asin')
        if asin and asin not in asins:
            asins.append(asin)
        if len(asins) >= limit:
            break

    # fallback: find /dp/ASIN links
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
    title = (soup.find(id='productTitle') or soup.find('span', class_='a-size-large')).get_text(strip=True) if soup.find(id='productTitle') else asin
    img = None
    img_tag = soup.find(id='landingImage') or soup.select_one('#imgTagWrapperId img')
    if img_tag and img_tag.get('src'):
        img = img_tag['src']
    return {'asin': asin, 'title': title, 'img': img, 'url': url}


# NOTE: The PA-API call is left as a placeholder. If you have PA API credentials you should implement
# a proper signed request following PA-API 5.0 doc. Otherwise the script will still create a useful HTML
# with title + image scraped from the product page.

def build_affiliate_link(asin):
    return f'https://www.amazon.se/dp/{asin}/?tag={ASSOCIATE_TAG}'


def generate_html(products, out_path='index.html'):
    with open(out_path, 'w', encoding='utf-8') as f:
        # For brevity the example writes a minimal page. Use the index.html template above in production.
        f.write('<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
        f.write('<title>Top 10 Amazon.se Bestsellers</title><style>body{font-family:Arial;background:#f6f7f9;padding:20px} .card{background:#fff;padding:12px;border-radius:8px;margin-bottom:12px;display:flex;gap:12px}</style></head><body>')
        f.write('<h1>Top 10 Bestsellers on Amazon.se</h1>')
        for p in products:
            f.write(f"<article class='card'>\n")
            if p.get('img'):
                f.write(f"<img src='{p['img']}' width='90' style='object-fit:contain' alt=''>")
            f.write(f"<div><h2 style='margin:0 0 6px'>{p['title']}</h2>\n")
            f.write(f"<a href='{build_affiliate_link(p['asin'])}' target='_blank' rel='noopener'>Buy on Amazon</a></div></article>\n")
        f.write('</body></html>')


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


