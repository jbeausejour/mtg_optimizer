import logging
import random
from functools import partial

import pandas as pd
import pulp
from deap import algorithms, base, creator, tools

from app.extensions import db
from app.models.card import UserBuylistCard

logger = logging.getLogger(__name__)

# Removed MarketplaceCard, using mtgsdk instead for card fetching
from mtgsdk import Card

class PurchaseOptimizer:
    def run_optimization(self, card_names, sites, config):
        # Fetch card details dynamically using mtgsdk
        card_details = [Card.where(name=card_name).all()[0] for card_name in card_names]
        card_details_df = pd.DataFrame([card.__dict__ for card in card_details])
        buylist_df = pd.read_sql(
            UserBuylistCard.query.statement, db.session.bind
        )

        # Filter card_details_df to only include cards in the buylist
        card_details_df = card_details_df[card_details_df["name"].isin(
            buylist_df["name"])]

        # Optimization logic remains unchanged
        if config["milp_strat"]:
            results, iterations = self.run_milp_optimization()
        elif config["nsga_algo_strat"]:
            results = self.run_nsga_ii_optimization()
        elif config["hybrid_strat"]:
            milp_solution, _ = self.run_milp_optimization()
            results = self.run_nsga_ii_optimization(milp_solution)
        else:
            raise ValueError("No valid optimization strategy specified in config")

        # Process results
        if isinstance(results, pd.DataFrame):
            sites_results = results.to_dict("records")
        else:
            sites_results = [self.get_purchasing_plan(solution) for solution in results]

        return {
            "sites_results": sites_results,
            "iterations": iterations if "iterations" in locals() else None,
        }