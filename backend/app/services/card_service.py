import requests
import logging
import time
import random
import json
import pandas as pd
from datetime import datetime, timedelta, timezone

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app import db
from app.utils.selenium_driver import SeleniumDriver
from app.models.card_data import CardData
from app.models.card import Card, Card_list
from app.models.sets import Sets
from app.utils.data_fetcher import DataFetcher
from app.utils.optimization import OptimizationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"
SCRYFALL_SEARCH_API_URL = "https://api.scryfall.com/cards/search"
CARDCONDUIT_URL = "https://cardconduit.com/buylist"

class CardService:
    @staticmethod
    def get_all_cards():
        print('Getting cards!')
        return Card_list.query.all()

    @staticmethod
    def get_recent_card_data(card_name):
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_data = CardData.query.filter_by(card_name=card_name).filter(CardData.scan_timestamp > one_hour_ago).first()
        
        if recent_data:
            return {
                'scryfall': {
                    'name': recent_data.card_name,
                    'oracle_id': recent_data.oracle_id,
                    'multiverse_ids': list(map(int, recent_data.multiverse_ids.split(','))),
                    'reserved': recent_data.reserved,
                    'lang': recent_data.lang,
                    'set': recent_data.set_code,
                    'set_name': recent_data.set_name,
                    'collector_number': recent_data.collector_number,
                    'variation': recent_data.variation,
                    'promo': recent_data.promo,
                    'prices': json.loads(recent_data.prices),
                    'purchase_uris': json.loads(recent_data.purchase_uris)
                },
                'cardconduit': json.loads(recent_data.cardconduit_data),
                'purchase_data': json.loads(recent_data.purchase_data),
                'scan_timestamp': recent_data.scan_timestamp.isoformat()
            }
        return None

    @staticmethod
    def get_card_versions(card_name):
        response = requests.get(SCRYFALL_SEARCH_API_URL, params={'q': f'!"{card_name}"'})
        response.raise_for_status()
        
        data = response.json()
        sets = set()
        languages = set()
        versions = set()

        for card in data['data']:
            sets.add((card['set'], card['set_name']))
            languages.add(card['lang'])
            if 'finishes' in card:
                versions.update(card['finishes'])

        return {
            'name': card_name,
            'sets': [{'code': code, 'name': name} for code, name in sets],
            'languages': list(languages),
            'versions': list(versions)
        }
    
    @staticmethod
    def get_all_sets():
        print('Getting all sets!')
        try:
            # Check if we need to update the sets
            oldest_allowed_update = datetime.now() - timedelta(days=7)  # Update weekly
            outdated_sets = Sets.query.filter(Sets.last_updated < oldest_allowed_update).first()
            
            if outdated_sets or Sets.query.count() == 0:
                # Fetch and update sets from Scryfall
                CardService.fetch_sets_from_scryfall()     
                
            # Fetch sets from the database
            sets = Sets.query.order_by(Sets.release_date.desc()).all()
            print('sets are:', sets)
            return sets

        except Exception as e:
            logger.error(f"Error fetching sets: {str(e)}")
            return None

    @staticmethod
    def fetch_card_data(card_name, set_code=None, language=None, version=None):
        # Check for recent data first
        #recent_data = CardService.get_recent_card_data(card_name)
        #if recent_data:
        #    return recent_data

        scryfall_data = CardService.fetch_scryfall_data(card_name, set_code, language)
        
        # Fetch all printings
        all_parts = CardService.fetch_all_printings(scryfall_data.get('prints_search_uri'))
        scryfall_data['all_parts'] = all_parts

        #cardconduit_data = CardService.fetch_cardconduit_data(card_name, set_code)
        
        # Add version information to Scryfall data
        #scryfall_data['version'] = version

        # Fetch prices from purchase URIs
        #purchase_data = CardService.fetch_purchase_data(scryfall_data.get('purchase_uris', {}))

        # Combine all data
        combined_data = {
            'scryfall': scryfall_data,
            #'cardconduit': cardconduit_data,
            #'purchase_data': purchase_data,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Store the combined data
        #CardService.store_card_data(combined_data)

        return combined_data

    @staticmethod
    def fetch_scryfall_data(card_name, set_code=None, language=None):
        params = {'fuzzy': card_name}
        if set_code:
            params['set'] = set_code
        if language:
            params['lang'] = language

        response = requests.get(SCRYFALL_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Extract required fields
        required_fields = [
            'oracle_id', 'multiverse_ids', 'reserved', 'name', 'lang',
            'set', 'set_name', 'collector_number', 'variation', 'promo',
            'prices', 'purchase_uris'
        ]
        return data

    @staticmethod
    def fetch_sets_from_scryfall():
        response = requests.get('https://api.scryfall.com/sets')
        response.raise_for_status()
        sets_data = response.json()['data']
        for set_info in sets_data:
            if set_info['set_type'] in ['core', 'expansion', 'masters', 'draft_innovation', 'commander']:
                magic_set = Sets.query.filter_by(set_code=set_info['code']).first()
                if not magic_set:
                    magic_set = Sets(
                        set_code=set_info['code'],
                        set_name=set_info['name'],
                        set_type=set_info['set_type'],
                        release_date=datetime.strptime(set_info['release_date'], '%Y-%m-%d').date() if set_info['release_date'] else None
                    )
                    db.session.add(magic_set)
                else:
                    magic_set.set_name = set_info['name']
                    magic_set.set_type = set_info['set_type']
                    magic_set.release_date = datetime.strptime(set_info['release_date'], '%Y-%m-%d').date() if set_info['release_date'] else None
                magic_set.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        return sets_data
        
    @staticmethod
    def fetch_all_printings(prints_search_uri):
        response = requests.get(prints_search_uri)
        response.raise_for_status()
        data = response.json()
        
        all_parts = []
        for card in data.get('data', []):
            all_parts.append({
                'set': card.get('set'),
                'set_name': card.get('set_name'),
                'prices': card.get('prices'),
                'scryfall_uri': card.get('scryfall_uri')
            })
        
        return all_parts
    
    @staticmethod
    def fetch_additional_data(card_name, set_code):
        cardconduit_data = CardService.fetch_cardconduit_data(card_name, set_code)
        purchase_data = CardService.fetch_purchase_data(cardconduit_data.get('purchase_uris', {}))
        
        # Update the stored data
        card_data = CardData.query.filter_by(card_name=card_name).first()
        if card_data:
            card_data.cardconduit_data = json.dumps(cardconduit_data)
            card_data.purchase_data = json.dumps(purchase_data)
            card_data.last_additional_data_fetch = datetime.now(timezone.utc)
            db.session.commit()

    def fetch_cardconduit_data(cardname, set_code):
        # Check if we have recent data (less than a day old)
        recent_data = CardService.get_recent_card_data(cardname)
        if recent_data:
            return recent_data['cardconduit']

        driver = SeleniumDriver.get_driver()
        wait = WebDriverWait(driver, 10)  # 10 seconds timeout
        
        params = {
            "cardname": cardname,
            "set_code": set_code,
            "price_lte": "",
            "price_gte": "",
            "sort": "name-asc",
            "finish": "",
            "page": "1"
        }
        try:
            driver.get(CARDCONDUIT_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
            
            # Wait for the page to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.border-b.border-gray-200.py-6')))
            
            # Scroll to the bottom of the page
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for any dynamic content to load after scrolling
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table.whitespace-nowrap.text-sm.border')))
            
            results = []
            card_entries = driver.find_elements(By.CSS_SELECTOR, 'div.border-b.border-gray-200.py-6')
            
            for entry in card_entries:
                name_div = entry.find_element(By.CSS_SELECTOR, 'div.text-sm.sm\\:text-lg.flex.items-center.flex-no-wrap')
                if name_div and cardname.lower() in name_div.text.strip().lower():
                    set_info_div = entry.find_element(By.CSS_SELECTOR, 'div.text-xs.sm\\:text-base.font-sans')
                    set_info = set_info_div.text.strip() if set_info_div else 'N/A'
                    
                    price_div = entry.find_element(By.CSS_SELECTOR, 'div.p-6.xl\\:p-8.pb-0.font-mono.w-full')
                    retail_price = 'Unavailable'
                    if price_div:
                        price_text = price_div.find_element(By.CSS_SELECTOR, 'div.text-xs.sm\\:text-base')
                        retail_price = price_text.text.strip() if price_text else 'Unavailable'
                    
                    buylist_table = entry.find_element(By.CSS_SELECTOR, 'table.whitespace-nowrap.text-sm.border')
                    buylist_prices = {}
                    if buylist_table:
                        rows = buylist_table.find_elements(By.TAG_NAME, 'tr')[1:]  # Skip header row
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) >= 2:
                                service = cells[1].text.strip()
                                price = cells[0].text.strip()
                                buylist_prices[service] = price
                    
                    results.append({
                        'name': name_div.text.strip(),
                        'set_info': set_info,
                        'retail_price': retail_price,
                        'buylist_prices': buylist_prices
                    })
            
            return results
        
        except Exception as e:
            print(f"An error occurred while fetching CardConduit data: {e}")
            return {'error': str(e)}
        
        finally:
            driver.quit()

    @staticmethod
    def fetch_purchase_data(purchase_uris):
        purchase_data = {}
        for site, url in purchase_uris.items():
            if (site != 'cardmarket' and site != 'cardhoarder'):  # Temporarily disable CardMarket & cardhoarder
                purchase_data[site] = CardService.scrape_price(url)
        return purchase_data
    
    @staticmethod
    def scrape_price(url, max_retries=3, use_headless=True):  # Reduced retries and added headless option
        driver = SeleniumDriver.get_driver(use_headless)
        
        try:
            driver.get(url)
            time.sleep(random.uniform(2, 4))
            
            if "tcgplayer.com" in url:
                # Extract product name and set info
                product_info = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product-details__name"))
                ).text
                
                # Extract price points
                price_points = {}
                price_table = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "section.price-points.price-guide__points table"))
                )
                rows = price_table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) == 2:
                        price_points[cells[0].text] = cells[1].text

                # Extract latest sales
                latest_sales = []
                sales_section = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "section.price-guide__latest-sales"))
                )
                sales = sales_section.find_elements(By.CSS_SELECTOR, "div.latest-sales > div")
                for sale in sales[:3]:  # Get the last 3 sales
                    date = sale.find_element(By.CSS_SELECTOR, "span.date").text
                    condition = sale.find_element(By.CSS_SELECTOR, "span.condition").text
                    quantity = sale.find_element(By.CSS_SELECTOR, "span.quantity").text
                    price = sale.find_element(By.CSS_SELECTOR, "span.price").text
                    latest_sales.append({
                        "date": date,
                        "condition": condition,
                        "quantity": quantity,
                        "price": price
                    })

                return {
                    "product_info": product_info,
                    "price_points": price_points,
                    "latest_sales": latest_sales
                }
            ##elif "cardmarket.com" in url:
            ##    price_element = WebDriverWait(driver, 10).until(
            ##        EC.presence_of_element_located((By.CSS_SELECTOR, ".col-6 .font-weight-bold"))
            ##    )
            elif "cardkingdom.com" in url:
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".stylePrice"))
                )
            #elif "cardhoarder.com" in url:  # Added support for CardHoarder
            #    price_element = WebDriverWait(driver, 10).until(
            #        EC.presence_of_element_located((By.CSS_SELECTOR, ".price"))
            #    )
            else:
                raise ValueError(f"Unsupported site: {url}")
            
            return price_element.text.strip()
        
        except Exception as e:
            print(f"An error occurred while scraping price from {url}: {e}")
            if max_retries > 0:
                time.sleep(random.uniform(1, 3))
                return CardService.scrape_price(url, max_retries - 1, use_headless)
            return None
        
        finally:
            driver.quit()

    @staticmethod
    def rotate_proxy():
        # Placeholder for proxy rotation implementation
        # This method should return a new proxy configuration
        pass

    @staticmethod
    def store_card_data(data):
        card_data = CardData(
            card_name=data['scryfall']['name'],
            oracle_id=data['scryfall']['oracle_id'],
            multiverse_ids=','.join(map(str, data['scryfall'].get('multiverse_ids', []))),
            reserved=data['scryfall'].get('reserved', False),
            lang=data['scryfall'].get('lang', ''),
            set_code=data['scryfall'].get('set', ''),
            set_name=data['scryfall'].get('set_name', ''),
            collector_number=data['scryfall'].get('collector_number', ''),
            variation=data['scryfall'].get('variation', False),
            promo=data['scryfall'].get('promo', False),
            prices=json.dumps(data['scryfall'].get('prices', {})),
            purchase_uris=json.dumps(data['scryfall'].get('purchase_uris', {})),
            cardconduit_data=json.dumps(data['cardconduit']),
            #purchase_data=json.dumps(data['purchase_data']),
            scan_timestamp=datetime.now(timezone.utc)
        )
        
        db.session.add(card_data)
        db.session.commit()

    @staticmethod
    def get_recent_card_data(card_name):
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        recent_data = CardData.query.filter_by(card_name=card_name).filter(CardData.scan_timestamp > one_day_ago).first()
        
        if recent_data:
            return {
                'scryfall': {
                    'name': recent_data.card_name,
                    'oracle_id': recent_data.oracle_id,
                    'multiverse_ids': list(map(int, recent_data.multiverse_ids.split(','))),
                    'reserved': recent_data.reserved,
                    'lang': recent_data.lang,
                    'set': recent_data.set_code,
                    'set_name': recent_data.set_name,
                    'collector_number': recent_data.collector_number,
                    'variation': recent_data.variation,
                    'promo': recent_data.promo,
                    'prices': json.loads(recent_data.prices),
                    'purchase_uris': json.loads(recent_data.purchase_uris)
                },
                'cardconduit': json.loads(recent_data.cardconduit_data),
                'scan_timestamp': recent_data.scan_timestamp.isoformat()
            }
        return None

    @staticmethod
    async def update_card_data():
        await DataFetcher.update_all_cards()

    @staticmethod
    def optimize_card_purchases(strategy='milp', min_store=None, find_min_store=False):
        card_details_df = pd.read_sql(Card.query.statement, Card.query.session.bind)
        buylist_df = pd.read_sql(Card_list.query.statement, Card_list.query.session.bind)

        optimization_engine = OptimizationEngine(card_details_df, buylist_df)

        if strategy == 'milp':
            return optimization_engine.run_milp_optimization(min_store, find_min_store)
        elif strategy == 'nsga_ii':
            return optimization_engine.run_nsga_ii_optimization()
        elif strategy == 'hybrid':
            milp_solution, _ = optimization_engine.run_milp_optimization(min_store, find_min_store)
            return optimization_engine.run_nsga_ii_optimization(milp_solution)
        else:
            raise ValueError("Invalid optimization strategy")

    @staticmethod
    def get_purchasing_plan(solution):
        card_details_df = pd.read_sql(Card.query.statement, Card.query.session.bind)
        buylist_df = pd.read_sql(Card_list.query.statement, Card_list.query.session.bind)
        optimization_engine = OptimizationEngine(card_details_df, buylist_df)
        return optimization_engine.get_purchasing_plan(solution)