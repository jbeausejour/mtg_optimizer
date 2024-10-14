import pandas as pd
import pulp
from mtg_logger import *

logger = None


def set_milp_logger(new_logger):
    global logger
    logger = new_logger


def process_result(buy_vars, costs, limited_output, total_qty, card_details_df):
    Total_price = 0.0
    results = []
    total_card_nbr = 0

    # Iterate over each card and store combination
    for card, store_dict in buy_vars.items():
        for store, var in store_dict.items():
            quantity = var.value()
            if quantity > 0:  # If this variable is part of the solution
                price_per_unit = costs[card][store]
                card_store_total_price = quantity * price_per_unit

                if price_per_unit != 10000:
                    Total_price += card_store_total_price
                    total_card_nbr += quantity
                    # Find the original index of the card in card_details_df
                    original_index = card_details_df[
                        (card_details_df["Name"] == card)
                        & (card_details_df["Site"] == store)
                    ].index[0]
                    original_card = card_details_df.loc[original_index]

                    # Append the result to the list
                    results.append(
                        {
                            "Original_Index": original_index,
                            "Original_Card": original_card,
                            "Card": card,
                            "Store": store,
                            "Quantity": quantity,
                            "Price": price_per_unit,
                            "Total Price": card_store_total_price,
                        }
                    )

                # Log the message if not limited output
                if not limited_output:
                    message_type = "Cannot Buy" if price_per_unit == 10000 else "Buy"
                    message_color = "b_red" if price_per_unit == 10000 else "b_green"
                    message = [
                        ("[INFO] ", "d_yellow"),
                        (f"{message_type} ", "rst"),
                        (f"{quantity} ", "b_cyan"),
                        ("x ", "rst"),
                        (f"{card} ", "b_cyan"),
                        ("from ", "rst"),
                        (
                            f"{store if price_per_unit != 10000 else 'any stores'} ",
                            message_color,
                        ),
                        ("at a price of ", "rst"),
                        (f"${price_per_unit} ", message_color),
                        ("each, totalizing ", "rst"),
                        (f"${card_store_total_price}", message_color),
                    ]
                    logger.info(color_msg(message))

    # Create and sort the DataFrame
    results_df = pd.DataFrame(results)
    sorted_results_df = results_df.sort_values(by=["Store", "Card"])
    sorted_results_df.reset_index(drop=True, inplace=True)

    # Log additional information
    num_stores_used = results_df["Store"].nunique()
    store_usage_counts = sorted_results_df[sorted_results_df["Price"] != 10000][
        "Store"
    ].value_counts()
    store_usage_str = ", ".join(
        [f"{store}: {count}" for store, count in store_usage_counts.items()]
    )

    if not limited_output:
        logger.info(
            color_msg(
                [
                    ("[INFO] ", "d_yellow"),
                    ("Minimum number of different sites to order from: ", "rst"),
                    (f"{num_stores_used}", "b_green"),
                ]
            )
        )
        logger.info(
            color_msg(
                [
                    ("[INFO] ", "d_yellow"),
                    ("Sites to order from: ", "rst"),
                    (store_usage_str, "b_green"),
                ]
            )
        )
        logger.info(
            color_msg(
                [
                    ("[INFO] ", "d_yellow"),
                    ("Total price of all purchases ", "rst"),
                    (f"${Total_price:.2f}", "b_green"),
                ]
            )
        )
        logger.info(
            color_msg(
                [
                    ("[INFO] ", "d_yellow"),
                    ("Total number of cards purchased: ", "rst"),
                    (f"{total_card_nbr}/{total_qty}", "b_green"),
                ]
            )
        )
    iteration_results = {
        "nbr_card_in_solution": total_card_nbr,
        "Total_price": Total_price,
        "Number_store": num_stores_used,
        "List_stores": store_usage_str,
        "sorted_results_df": sorted_results_df,
    }
    return iteration_results


def run_pulp(
    standardized_cards_df, available_cards_to_buy_df, min_store, find_min_store
):

    # Extract unique cards and stores
    unique_cards = available_cards_to_buy_df["Name"].unique()
    unique_stores = standardized_cards_df["Site"].unique()
    total_qty = len(available_cards_to_buy_df)

    # A high cost to assign for unavailable card-store combinations
    high_cost = 10000  # Adjust this value as needed

    # Create a dictionary of costs for each card in each store
    costs = {}
    for card in unique_cards:
        costs[card] = {}
        for store in unique_stores:
            price = standardized_cards_df[
                (standardized_cards_df["Name"] == card)
                & (standardized_cards_df["Site"] == store)
            ]["Weighted_Price"].min()
            if pd.isna(price):  # If the price is NaN, assign a high cost
                costs[card][store] = high_cost
            else:
                costs[card][store] = price

    all_iterations_results = []
    no_optimal_found = False
    if find_min_store == False:

        prob, buy_vars = setup_prob(
            costs, unique_cards, unique_stores, available_cards_to_buy_df, min_store
        )
        # Check if the problem was solved successfully
        if pulp.LpStatus[prob.status] != "Optimal":
            print("Solver did not find an optimal solution.")
            no_optimal_found = True

        if no_optimal_found:
            return None
        else:
            all_iterations_results = process_result(
                buy_vars, costs, False, total_qty, standardized_cards_df
            )
            return all_iterations_results[0]["sorted_results_df"], None
    else:
        message = [("[INFO] ", "d_yellow"), ("Starting iterative algo", "rst")]
        logger.info(color_msg(message))
        still_going = True
        iteration = 1
        current_min = min_store
        while still_going and current_min >= 1:

            message = [
                ("[info] ", "d_yellow"),
                ("Iteration [", "rst"),
                (f"{iteration}", "d_cyan"),
                ("]: Current number of diff. stores: ", "rst"),
                (f"{current_min}", "d_cyan"),
            ]
            logger.info(color_msg(message))

            prob, buy_vars = setup_prob(
                costs,
                unique_cards,
                unique_stores,
                available_cards_to_buy_df,
                current_min,
            )

            # Check if the problem was solved successfully
            if pulp.LpStatus[prob.status] != "Optimal":
                print("Solver did not find an optimal solution.")
                still_going = False
            else:
                limited_output = True
                iteration_results = process_result(
                    buy_vars, costs, limited_output, total_qty, standardized_cards_df
                )
                all_iterations_results.append(iteration_results)

                message_color = (
                    "b_red"
                    if iteration_results["nbr_card_in_solution"] != total_qty
                    else "b_green"
                )
                message = [
                    ("[info] ", "d_yellow"),
                    ("Iteration [", "rst"),
                    (f"{iteration}", "d_cyan"),
                    ("]: Total price ", "rst"),
                    (f"{iteration_results['Total_price']:.2f}$ ", "d_cyan"),
                    (
                        f"{int(iteration_results['nbr_card_in_solution'])}/{total_qty}",
                        message_color,
                    ),
                ]
                logger.info(color_msg(message))

                iteration += 1
                current_min -= 1

        if no_optimal_found:
            return None
        else:
            # Initialize with the first iteration's results
            least_expensive_and_complete_iteration = all_iterations_results[0]
            min_total_price = least_expensive_and_complete_iteration["Total_price"]

            # Iterate through all iterations to find the least expensive one
            for iteration_result in all_iterations_results:
                if (
                    iteration_result["Total_price"] < min_total_price
                    and iteration_results["nbr_card_in_solution"] == total_qty
                ):
                    min_total_price = iteration_result["Total_price"]
                    least_expensive_and_complete_iteration = iteration_result

            message = [
                ("[INFO] ", "d_yellow"),
                ("Best Iteration is with ", "rst"),
                (
                    f"{least_expensive_and_complete_iteration['Number_store']}",
                    "d_green",
                ),
                (" stores with a total price of: ", "rst"),
                (
                    f"{least_expensive_and_complete_iteration['Total_price']:.2f}$",
                    "d_cyan",
                ),
            ]
            logger.info(color_msg(message))

            message = [
                ("[INFO] ", "d_yellow"),
                ("Using these 'stores: #cards': ", "rst"),
            ]
            logger.info(color_msg(message))
            for store in least_expensive_and_complete_iteration["List_stores"].split(
                ","
            ):
                message = [("[INFO] ", "d_yellow"), (f"{store}", "d_cyan")]
                logger.info(color_msg(message))

            return (
                least_expensive_and_complete_iteration["sorted_results_df"],
                all_iterations_results,
            )


def setup_prob(costs, unique_cards, unique_stores, buylist, min_store):
    # Create a LP problem
    prob = pulp.LpProblem("MTGCardOptimization", pulp.LpMinimize)

    # Variables: whether to buy a card from a specific store
    buy_vars = pulp.LpVariable.dicts(
        "Buy", (unique_cards, unique_stores), 0, 1, pulp.LpBinary
    )
    store_vars = pulp.LpVariable.dicts(
        "Store", unique_stores, 0, 1, pulp.LpBinary)

    # Objective: Minimize cost
    prob += pulp.lpSum(
        [
            buy_vars[card][store] * costs[card][store]
            for card in unique_cards
            for store in unique_stores
        ]
    )

    # Constraints: Ensure each card is bought in the required quantity
    for card in unique_cards:
        required_quantity = buylist[buylist["Name"]
                                    == card]["Quantity"].iloc[0]
        prob += (
            pulp.lpSum([buy_vars[card][store] for store in unique_stores])
            == required_quantity
        )

    for store in unique_stores:
        prob += store_vars[store] >= pulp.lpSum(
            buy_vars[card][store] for card in unique_cards
        ) / len(unique_cards)

    prob += pulp.lpSum(store_vars[store]
                       for store in unique_stores) <= min_store
    # Solve the problem without printing solver messages
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    return prob, buy_vars
