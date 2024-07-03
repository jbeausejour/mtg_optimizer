import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.utils.selenium_driver import SeleniumDriver
from app.models.card_data import CardData
from app.models.card import Card, Card_list
from app import db
from app.utils.data_fetcher import DataFetcher
from app.utils.optimization import OptimizationEngine
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import json

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"
SCRYFALL_SEARCH_API_URL = "https://api.scryfall.com/cards/search"
CARDCONDUIT_URL = "https://cardconduit.com/buylist"

class CardService:
    @staticmethod
    def get_all_cards():
        print('Getting cards!')
        return Card_list.query.all()

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
    def fetch_card_data(card_name, set_code=None, language=None, version=None):
        scryfall_data = CardService.fetch_scryfall_data(card_name, set_code, language)
        cardconduit_data = CardService.fetch_cardconduit_data(card_name)
        
        # Add version information to Scryfall data
        scryfall_data['version'] = version

        # Fetch prices from purchase URIs
        purchase_data = CardService.fetch_purchase_data(scryfall_data['purchase_uris'])

        # Combine all data
        combined_data = {
            'scryfall': scryfall_data,
            'cardconduit': cardconduit_data,
            'purchase_data': purchase_data,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Store the combined data
        CardService.store_card_data(combined_data)

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
        return {field: data.get(field) for field in required_fields}

    @staticmethod
    def fetch_cardconduit_data(cardname):
        # Check if we have recent data (less than a day old)
        recent_data = CardService.get_recent_card_data(cardname)
        if recent_data:
            return recent_data['cardconduit']

        driver = SeleniumDriver.get_driver()
        
        params = {
            "cardname": cardname,
            "set_code": "",
            "price_lte": "",
            "price_gte": "",
            "sort": "name-asc",
            "finish": "",
            "page": "1"
        }
        try:
            driver.get(CARDCONDUIT_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
            time.sleep(random.uniform(3, 5))
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "pre"))
            )
            
            json_element = driver.find_element(By.CSS_SELECTOR, "pre")
            json_text = json_element.text
            data = json.loads(json_text)
            
            return data
        
        except Exception as e:
            print(f"An error occurred while fetching CardConduit data: {e}")
            return {'error': str(e)}
        
        finally:
            driver.quit()

    @staticmethod
    def fetch_purchase_data(purchase_uris):
        purchase_data = {}
        for site, url in purchase_uris.items():
            purchase_data[site] = CardService.scrape_price(url)
        return purchase_data

    @staticmethod
    def scrape_price(url):
        driver = SeleniumDriver.get_driver()
        
        try:
            driver.get(url)
            time.sleep(random.uniform(2, 4))
            
            if "tcgplayer.com" in url:
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".inventory__price-with-shipping"))
                )
            elif "cardmarket.com" in url:
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".col-6 .font-weight-bold"))
                )
            elif "cardkingdom.com" in url:
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".stylePrice"))
                )
            else:
                raise ValueError(f"Unsupported site: {url}")
            
            return price_element.text.strip()
        
        except Exception as e:
            print(f"An error occurred while scraping price from {url}: {e}")
            return None
        
        finally:
            driver.quit()

    @staticmethod
    def store_card_data(data):
        card_data = CardData(
            card_name=data['scryfall']['name'],
            oracle_id=data['scryfall']['oracle_id'],
            multiverse_ids=','.join(map(str, data['scryfall']['multiverse_ids'])),
            reserved=data['scryfall']['reserved'],
            lang=data['scryfall']['lang'],
            set_code=data['scryfall']['set'],
            set_name=data['scryfall']['set_name'],
            collector_number=data['scryfall']['collector_number'],
            variation=data['scryfall']['variation'],
            promo=data['scryfall']['promo'],
            prices=json.dumps(data['scryfall']['prices']),
            purchase_uris=json.dumps(data['scryfall']['purchase_uris']),
            cardconduit_data=json.dumps(data['cardconduit']),
            scan_timestamp=datetime.utcnow()
        )
        
        db.session.add(card_data)
        db.session.commit()

    @staticmethod
    def get_recent_card_data(card_name):
        one_day_ago = datetime.utcnow() - timedelta(days=1)
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