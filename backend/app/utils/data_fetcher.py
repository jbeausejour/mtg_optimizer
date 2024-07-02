# data_fetcher.py

import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

from app.models.site import Site
from app.models.card import Card, Card_list
from app.models.scan import Scan, ScanResult
from backend.app import db


logger = logging.getLogger(__name__)

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
    def extract_info(soup, site, card_names):
        # We'll refactor this method separately
        pass

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