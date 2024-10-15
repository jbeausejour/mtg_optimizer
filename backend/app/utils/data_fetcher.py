import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup

from app.extensions import db
from app.models.card import UserBuylistCard
from app.models.scan import Scan, ScanResult
from app.models.site import Site
from app.utils.helpers import parse_card_string
from mtgsdk import Card  # Importing mtgsdk to dynamically fetch card data

logger = logging.getLogger(__name__)


class ExternalDataSynchronizer:
    # Removed references to MarketplaceCard, using mtgsdk instead for fetching card data
    
    @staticmethod
    async def update_all_cards():
        card_query = (
            UserBuylistCard.query.with_entities(
                UserBuylistCard.name).distinct().all()
        )
        card_names = [card.name for card in card_query]
        sites = Site.query.filter_by(active=True).all()

        async with ExternalDataSynchronizer() as fetcher:
            tasks = [fetcher.process_site(site, card_names) for site in sites]
            await asyncio.gather(*tasks)

    @staticmethod
    def save_cards_to_db(site, cards_df):
        logger.info(f"Saving to DB")
        try:
            scan = Scan()
            db.session.add(scan)
            db.session.commit()

            for _, card_data in cards_df.iterrows():
                # Using card_name directly instead of creating a MarketplaceCard
                scan_result = ScanResult(
                    scan_id=scan.id,
                    card_name=card_data["Name"],
                    site_id=site.id,
                    price=card_data["Price"],
                )
                db.session.add(scan_result)
            db.session.commit()
            logger.info(
                f"Successfully saved scan results for {site.name} with {len(cards_df)} cards."
            )
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Error saving cards to database for site {site.name}: {str(e)}"
            )
            raise
        finally:
            db.session.close()