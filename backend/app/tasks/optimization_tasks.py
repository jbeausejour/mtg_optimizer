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
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
import asyncio
from sqlalchemy import select

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


@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def start_scraping_task(self, site_ids, card_list, strategy, min_store, find_min_store):
    logger = logging.getLogger("celery_task_logger")
    logger.info(f"Task {self.request.id} - start_scraping_task is running")
    self.update_state(state="PROCESSING", meta={"status": "Initializing scraping task"})

    try:
        # Update initial state
        self.update_state(
            state="PROCESSING",
            meta={
                "status": "Task initialized",
                "progress": 0
            }
        )

        # Fetch the list of sites to scrape
        sites = Site.query.filter(Site.id.in_(site_ids)).all()
        logger.info(f"Starting scraping task for {len(sites)} sites with {len(card_list)} cards")
        
        # Extract card names from card_list
        card_names = [card['name'] for card in card_list if 'name' in card]
        
        # Check for outdated cards using names only
        outdated_cards = [card for card in card_list if not is_data_fresh(card['name'])]
        logger.info(f"Found {len(outdated_cards)} outdated cards that need updating")
        
        # If any cards are outdated, initiate scraping
        if outdated_cards:
            logger.info(f"Starting scraping process with strategy: {strategy}")
            scraper = ExternalDataSynchronizer()
            
            # Run the async scraping in the sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                logger.info("Initializing scraping loop")
                # Pass only the names to the scraper
                results = loop.run_until_complete(
                    scraper.scrape_multiple_sites(sites, card_names, strategy=strategy)
                )
                logger.info(f"Scraping completed. Retrieved {len(results) if results else 0} results")
            except Exception as e:
                logger.error(f"Error during scraping loop: {str(e)}")
                raise
            finally:
                logger.info("Closing scraping loop")
                loop.close()

            # Update progress during scraping
            self.update_state(
                state="PROCESSING",
                meta={
                    "status": "Scraping card data",
                    "progress": 25,
                    "cards_total": len(outdated_cards)
                }
            )

        # Safely handle empty datasets
        try:
            BATCH_SIZE = 1000
            card_details = []
            total_records = ScanResult.query.count()
            
            if total_records == 0:
                logger.warning("No scan results found in database")
                card_details_df = pd.DataFrame()
            else:
                for offset in range(0, total_records, BATCH_SIZE):
                    batch = pd.read_sql(
                        Query(ScanResult).offset(offset).limit(BATCH_SIZE).statement,
                        db.session.bind
                    )
                    if not batch.empty:
                        card_details.append(batch)
                
                if card_details:
                    card_details_df = pd.concat(card_details, ignore_index=True)
                else:
                    card_details_df = pd.DataFrame()

            # Fix the SQLAlchemy query
            try:
                # Use SQLAlchemy properly with pandas
                query = select(UserBuylistCard)
                buylist_df = pd.read_sql_query(
                    query, 
                    db.session.bind,
                    index_col=None
                )
                
                if buylist_df.empty:
                    logger.warning("No buylist data found")
                    return {
                        "status": "Completed",
                        "message": "No buylist data to process",
                        "results": []
                    }
                    
                # ...rest of the optimization code...
                
            except Exception as e:
                logger.error(f"Database error: {str(e)}")
                raise

            optimizer = PurchaseOptimizer(card_details_df, buylist_df, config={
                "milp_strat": strategy == "milp",
                "nsga_algo_strat": strategy == "nsga-ii",
                "hybrid_strat": strategy == "hybrid",
                "min_store": min_store,
                "find_min_store": find_min_store,
            })
            
            # Update progress during optimization
            self.update_state(
                state="PROCESSING",
                meta={
                    "status": "Running optimization",
                    "progress": 75
                }
            )

            optimization_results = optimizer.run_optimization(card_list, sites, optimizer.config)

            return {
                "status": "Completed",
                "progress": 100,
                "sites_scraped": len(sites),
                "cards_scraped": len(card_list),
                "optimization": optimization_results,
            }

        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            raise

    except (SoftTimeLimitExceeded, TimeLimitExceeded) as e:
        logger.error("Task timed out: %s", str(e))
        self.update_state(state=states.FAILURE, meta={"error": "Task timed out"})
        raise
    except Exception as e:
        logger.exception("Error during scraping task")
        self.update_state(state=states.FAILURE, 
                         meta={
                             "exc_type": type(e).__name__, 
                             "exc_message": str(e),
                             "step": "scraping"
                         })
        db.session.rollback()
        raise e  # Raising the exception again so Celery knows it failed


# Remove async from optimize_cards task
@celery_app.task(bind=True)
def optimize_cards(self, card_list_dicts, site_ids):
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
            site_results = scraper.scrape_multiple_sites([site], cards, strategy=strategy)
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
