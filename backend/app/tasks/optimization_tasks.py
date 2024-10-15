import logging
import datetime
from sqlalchemy.orm import Query
import pandas as pd
from flask import current_app
from mtgsdk import Card  # Importing mtgsdk to dynamically fetch card data
from app.extensions import db
from app.models.scan import Scan, ScanResult
from app.models.site import Site
from app.utils.data_fetcher import ExternalDataSynchronizer
from app.utils.optimization import PurchaseOptimizer
from app.models.card import UserBuylistCard
from .celery_app import celery_app
from celery import states

# Configure a logger specifically for Celery tasks
logger = logging.getLogger("celery_task_logger")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"))
    logger.addHandler(handler)

def is_data_fresh(card_name, freshness_threshold_hours=24):
    """ Check if data in ScanResult is fresh enough """
    scan_result = ScanResult.query.filter_by(card_name=card_name).order_by(ScanResult.updated_at.desc()).first()
    if scan_result:
        return (datetime.datetime.utcnow() - scan_result.updated_at).total_seconds() < freshness_threshold_hours * 3600
    return False


@celery_app.task(bind=True)
async def start_scraping_task(self, site_ids, card_list, strategy, min_store, find_min_store):
    logger = logging.getLogger("celery_task_logger")
    logger.info(f"Task {self.request.id} - start_scraping_task is running")
    self.update_state(state="PROCESSING", meta={"status": "Initializing scraping task"})

    try:
        # Fetch the list of sites to scrape
        sites = Site.query.filter(Site.id.in_(site_ids)).all()

        # Check for outdated cards
        outdated_cards = [card for card in card_list if not is_data_fresh(card['name'])]
        
        # If any cards are outdated, initiate scraping
        if outdated_cards:
            logger.info(f"Updating outdated cards: {outdated_cards}")
            scraper = ExternalDataSynchronizer()
            await scraper.scrape_multiple_sites(sites, outdated_cards, strategy=strategy)


        # Continue with optimization after ensuring data is up-to-date
        card_details_df = pd.read_sql(Query(ScanResult).statement, db.session.bind)
        buylist_df = pd.read_sql(Query(UserBuylistCard).statement, db.session.bind)

        # config = {
        #     "filename": f"optimization_task_{new_scan.id}",
        #     "log_level_file": current_app.config.get("LOG_LEVEL_FILE", "INFO"),
        #     "log_level_console": current_app.config.get("LOG_LEVEL_CONSOLE", "INFO"),
        #     "special_site_flag": current_app.config.get("SPECIAL_SITE_FLAG", True),
        #     "milp_strat": current_app.config.get("MILP_STRAT", True),
        #     "hybrid_strat": current_app.config.get("HYBRID_STRAT", False),
        #     "nsga_algo_strat": current_app.config.get("NSGA_ALGO_STRAT", False),
        #     "min_store": current_app.config.get("MIN_STORE", 1),
        #     "find_min_store": current_app.config.get("FIND_MIN_STORE", False),
        # }
        
        optimizer = PurchaseOptimizer(card_details_df, buylist_df, config={
            "milp_strat": strategy == "milp",
            "nsga_algo_strat": strategy == "nsga-ii",
            "hybrid_strat": strategy == "hybrid",
            "min_store": min_store,
            "find_min_store": find_min_store,
        })
        
        optimization_results = optimizer.run_optimization(card_list, sites, optimizer.config)

        return {
            "status": "Scraping and update completed",
            "sites_scraped": len(sites),
            "cards_scraped": len(card_list),
            "optimization": optimization_results,
        }

    except Exception as e:
        logger.exception("Error during scraping task")
        # Update the state to FAILURE with the appropriate message
        self.update_state(state=states.FAILURE, meta={"exc_type": type(e).__name__, "exc_message": str(e)})
        db.session.rollback()
        raise e  # Raising the exception again so Celery knows it failed


@celery_app.task(bind=True)
async def optimize_cards(self, card_list_dicts, site_ids):
    try:
        # Create a new scan
        new_scan = Scan()
        db.session.add(new_scan)
        db.session.commit()

        # Fetch full card objects and sites
        cards = UserBuylistCard.query.filter(
            UserBuylistCard.id.in_([card["id"] for card in card_list_dicts])
        ).all()
        sites = Site.query.filter(Site.id.in_(site_ids)).all()

        self.update_state(state="PROGRESS", meta={
                          "status": "Fetched cards and sites"})

        self.update_state(state="PROGRESS", meta={
                          "status": "Running optimization"})
        
        scraper = ExternalDataSynchronizer()
        all_results = []

        for site in sites:
            # Use the strategy defined for each site to scrape the card prices
            strategy = site.method  # Assuming each Site has a 'strategy' attribute
            self.update_state(state="PROGRESS", meta={
                              "status": f"Scraping data for site {site.name} with strategy {strategy}"})

            # Scrape card prices for this specific site
            site_results = await scraper.scrape_multiple_sites([site], cards, strategy=strategy)
            all_results.extend(site_results)

        self.update_state(state="PROGRESS", meta={"status": "Saving results"})

        # Save the scraped results to the database
        for result in all_results:
            scan_result = ScanResult(
                scan_id=new_scan.id,
                card_id=result["card_id"],
                site_id=result["site_id"],
                price=result["price"],
            )
            db.session.add(scan_result)

        db.session.commit()

        return {"status": "Optimization completed", "scan_id": new_scan.id}

    except Exception as e:
        logger.exception("Error during optimization")
        self.update_state(state="FAILURE", meta={"status": f"Error: {str(e)}"})
        db.session.rollback()
        return {"status": "Failed", "error": str(e)}
