import asyncio
import aiohttp
import logging
import re
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

from app.models.site import Site
from app.models.card import Card, Card_list
from app.models.scan import Scan, ScanResult
from app.utils.helpers import clean_card_name, parse_card_string, extract_numbers
from app.extensions import db

logger = logging.getLogger(__name__)

STRATEGY_ADD_TO_CART = 1
STRATEGY_SCRAPPER = 2
STRATEGY_HAWK = 3

class DataFetcher:
    def __init__(self):
        self.session = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    async def fetch_url(self, url):
        try:
            async with self.session.get(url) as response:
                return await response.text()
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def post_request(self, url, payload):
        try:
            async with self.session.post(url, data=payload) as response:
                return await response.text()
        except Exception as e:
            logger.error(f"Error posting to {url}: {str(e)}")
            return None

    async def search_crystalcommerce(self, site, card_names):
        search_url = site.url
        response_text = await self.fetch_url(search_url)
        if not response_text:
            return None

        soup = BeautifulSoup(response_text, "html.parser")
        auth_token_elem = soup.find("input", {"name": "authenticity_token"})
        if not auth_token_elem:
            return None

        auth_token = auth_token_elem["value"]
        cards_payload = "\r\n".join(card_names)
        payload = {
            "authenticity_token": auth_token,
            "query": cards_payload,
            "submit": "Continue",
        }

        response_text = await self.post_request(search_url, payload)
        return BeautifulSoup(response_text, "html.parser") if response_text else None

    async def process_site(self, site, card_names):
        soup = await self.search_crystalcommerce(site, card_names)
        if not soup:
            return

        cards_df = self.extract_info(soup, site, card_names)
        if cards_df is not None and not cards_df.empty:
            self.save_cards_to_db(site, cards_df, card_names)

    @staticmethod
    def save_cards_to_db(site, cards_df, card_names):
        scan = Scan(card_names=card_names)
        db.session.add(scan)
        db.session.commit()

        for _, card_data in cards_df.iterrows():
            card = Card(
                site=site.name,
                name=card_data['Name'],
                edition=card_data['Edition'],
                version=card_data.get('Version'),
                foil=card_data.get('Foil', False),
                quality=card_data['Quality'],
                language=card_data['Language'],
                quantity=card_data['Quantity'],
                price=card_data['Price']
            )
            db.session.add(card)
            db.session.flush()

            scan_result = ScanResult(
                scan_id=scan.id,
                card_id=card.id,
                site=site.name,
                price=card_data['Price']
            )
            db.session.add(scan_result)

        db.session.commit()

    @classmethod
    async def update_all_cards(cls):
        card_names = Card_list.query.with_entities(Card_list.name).distinct().all()
        card_names = [card.name for card in card_names]
        sites = Site.query.filter_by(active=True).all()

        async with cls() as fetcher:
            tasks = [fetcher.process_site(site, card_names) for site in sites]
            await asyncio.gather(*tasks)
    
    @staticmethod
    def extract_info(soup, site, card_names, strategy):
        if soup is None:
            logger.warning(f"Soup is None for site {site}")
            return pd.DataFrame()

        cards = []
        seen_variants = set()

        excluded_categories = {
            'playmats', 'booster packs', 'booster box', 'mtg booster boxes',
            'art series', 'fat packs and bundles', 'mtg booster packs',
            'magic commander deck', 'world championship deck singles',
            'The Crimson Moon\'s Fairy Tale', 'rpg accessories', 'scan other',
            'intro packs and planeswalker decks', 'wall scrolls'
        }

        if strategy == STRATEGY_HAWK:
            return pd.DataFrame([card.to_dict() for card in DataFetcher.strategy_hawk(soup)])

        content = soup.find('div', {'class': ['content', 'content clearfix', 'content inner clearfix']})
        if content is None:
            logger.error(f"Content div not found for site {site}")
            return pd.DataFrame()

        products_containers = content.find_all('div', {'class': 'products-container browse'})
        if not products_containers:
            logger.warning(f"No products container found for site {site}")
            return pd.DataFrame()

        for container in products_containers:
            for item in container.find_all('li', {'class': 'product'}):
                card = DataFetcher.process_product_item(item, site, card_names, excluded_categories)
                if card:
                    DataFetcher.process_variants(item, card, cards, seen_variants, strategy)

        return pd.DataFrame([card.to_dict() for card in cards])

    @staticmethod
    def process_product_item(item, site, card_names, excluded_categories):
        if DataFetcher.is_yugioh_card(item):
            return None

        meta = item.find('div', {'class': 'meta'})
        test_category = meta.find('span', {'class': 'category'}).text.strip()
        test_title = meta.find('h4', {'class': 'name'}).text.strip()

        if any(cat in test_category.lower() for cat in excluded_categories):
            return None

        card = parse_card_string(test_title)
        card.Site = site
        card.Name = clean_card_name(card.Name, card_names)
        card.Edition = test_category

        if not card.Name or card.Name not in card_names and card.Name.split(' // ')[0].strip() not in card_names:
            return None

        return card

    @staticmethod
    def process_variants(item, card, cards, seen_variants, strategy):
        variants = item.find('div', {'class': 'variants'})
        for variant in variants.find_all('div', {'class': 'variant-row'}):
            card_variant = DataFetcher.strategy_add_to_cart(card, variant) if strategy == STRATEGY_ADD_TO_CART else DataFetcher.strategy_scrapper(card, variant)
            if card_variant is not None and card_variant not in seen_variants:
                cards.append(card_variant)
                seen_variants.add(card_variant)

    @staticmethod
    def is_yugioh_card(item):
        image = item.find('div', {'class': 'image'})
        a_tag = image and image.find('a', href=True)
        return a_tag and 'yugioh' in a_tag['href']

    @staticmethod
    def strategy_add_to_cart(card, variant):
        if 'no-stock' in variant.get('class', []) or '0 In Stock' in variant:
            return None
        
        form_element = variant.find('form', {'class': 'add-to-cart-form'})
        if not form_element:
            return None

        attributes = form_element.attrs
        if 'data-name' not in attributes:
            return None

        unclean_name, product_version, product_foil = DataFetcher.find_name_version_foil(attributes['data-name'])

        if not card.Foil:
            card.Foil = product_foil
        if not card.Edition:
            card.Edition = product_version

        quality_language = DataFetcher.normalize_variant_description(attributes['data-variant'])
        quality, language = quality_language[:2]

        select_tag = variant.find('select', {'class': 'qty'}) or variant.find('input', {'class': 'qty'})
        qty_available = select_tag['max'] if select_tag and 'max' in select_tag.attrs else "0"

        card.Quality = quality
        card.Language = language
        card.Quantity = int(qty_available)
        card.Edition = attributes['data-category']
        card.Price = DataFetcher.normalize_price(attributes['data-price'])

        return card

    @staticmethod
    def strategy_scrapper(card, variant):
        if 'no-stock' in variant.get('class', []) or '0 In Stock' in variant:
            return None

        try:
            quality, language = DataFetcher.extract_quality_language(card, variant)
            if quality is None or language is None:
                return None

            quantity = DataFetcher.extract_quantity(card, variant)
            if quantity is None:
                return None

            price = DataFetcher.extract_price(card, variant)

            card.Quality = quality
            card.Language = language
            card.Quantity = quantity
            card.Price = price

            return card
        except Exception as e:
            logger.exception(f"Error in strategy_scrapper for {card.Name}: {str(e)}")
            return None

    @staticmethod
    def strategy_hawk(soup):
        cards_data = []
        for card_div in soup.select('.hawk-results__item'):
            card_details = {
                'name': card_div.select_one('.hawk-results__hawk-contentTitle').get_text(strip=True),
                'image_url': card_div.select_one('.hawk-results__item-image img')['src'],
                'edition': card_div.select_one('.hawk-results__hawk-contentSubtitle').get_text(strip=True),
                'variants': [],
                'stock': [],
                'prices': []
            }
            
            for variant_div in card_div.select('.hawk-results__hawk-contentVariants input[type="radio"]'):
                variant_details = {
                    'variant_id': variant_div['id'],
                    'condition': variant_div.get('data-options', '').split(',')[0].split('|')[1] if 'condition' in variant_div.get('data-options', '') else '',
                    'finish': variant_div.get('data-options', '').split(',')[1].split('|')[1] if 'finish' in variant_div.get('data-options', '') else ''
                }
                card_details['variants'].append(variant_details)
            
            for stock_span in card_div.select('.hawkStock'):
                card_details['stock'].append({
                    'variant_id': stock_span['data-var-id'],
                    'in_stock': stock_span.get_text(strip=True)
                })
            for price_span in card_div.select('.hawkPrice'):
                card_details['prices'].append({
                    'variant_id': price_span['data-var-id'],
                    'price': price_span.get_text(strip=True)
                })
            
            cards_data.append(card_details)
        
        return cards_data

    @staticmethod
    def find_name_version_foil(place_holder):
        items = re.split(r' - ', place_holder)
        items = [x.strip() for x in items]
        product_name = items[0]
        product_version = ""
        product_foil = ""

        for item in items[1:]:
            if "Foil" in item:
                product_foil = item
            else:
                product_version = item

        return product_name, product_version, product_foil

    @staticmethod
    def normalize_variant_description(variant_description):
        cleaned_description = variant_description.split(':')[-1].strip()
        variant_parts = cleaned_description.split(',')
        return [part.strip() for part in variant_parts]

    @staticmethod
    def extract_quality_language(card, variant):
        variant_description = variant.find('span', {'class': 'variant-short-info variant-description'}) or \
                              variant.find('span', {'class': 'variant-short-info'})
        if variant_description:
            quality_language = DataFetcher.normalize_variant_description(variant_description.text)
            return quality_language[:2]
        else:
            logger.error(f"Error in extract_quality_language for {card.Name}: variant-description not found")
            return None, None

    @staticmethod
    def extract_quantity(card, variant):
        variant_qty = variant.find('span', {'class': 'variant-short-info variant-qty'}) or \
                      variant.find('span', {'class': 'variant-short-info'})
        if variant_qty:
            variant_qty = variant_qty.text.strip()
            return extract_numbers(variant_qty)
        else:
            logger.error(f"Error in extract_quantity for {card.Name}: variant-qty not found")
            return None

    @staticmethod
    def extract_price(card, variant):
        price_elem = variant.find('span', {'class': 'regular price'})
        if price_elem is not None:
            price_text = price_elem.text
            return DataFetcher.normalize_price(price_text)
        else:
            logger.error(f"Error in extract_price for {card.Name}: Price element not found")
            return 0.0
