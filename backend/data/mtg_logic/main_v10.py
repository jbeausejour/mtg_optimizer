import datetime
import logging
import pandas as pd
import json
# import cProfile
# from memory_profiler import profile

# mine
import mtg_deap
import mtg_milp
from mtg_logger import *
from mtg_utils import *
from mtg_scrapper import *

########################################################################
# Start of the script
########################################################################


# Load the configuration file
with open('data/config.json', 'r') as config_file:
    config = json.load(config_file)
    # Flag indicating whether to consider sites with '--' in front
    special_site_flag = config["special_site_flag"]

    # Flag indicating whether to save all search to file
    save_all_results_to_csv = config["save_all_results_to_csv"]

    # Type of strategy to use
    best_site_strat = config["best_site_strat"]
    nsga_algo_strat = config["nsga_algo_strat"]
    milp_strat = config["milp_strat"]
    hybrid_strat = config["hybrid_strat"]
    
    #Target number of store
    min_store = config["min_store"]
    find_min_store = config["find_min_store"]
    
    use_previous_csv_results = config["use_previous_csv_results"]  
    
    #path related config
    sites_path = config["sites_path"]
    results_path = config["results_path"]
    data_path= config["data_path"]
    debug_mode = config["debug_mode"]


# Get current date
current_date = datetime.datetime.now().date()

# filename to store the logs
filename = f'log_file_{current_date}'

if(debug_mode):
    log_level_file = logging.DEBUG
    log_level_console = logging.DEBUG
else:
    log_level_file = logging.INFO
    log_level_console = logging.INFO
# log_level_console = logging.NOTSET

# Utilizing the configure_logger function from the mtg_logger module
logger = configure_logger(filename, log_level_file,
                          log_level_console, log_path='logs/')

# Assign the logger to utility modules using set_logger
set_utils_logger(get_logger())
set_scrapper_logger(get_logger())
mtg_deap.set_deap_logger(get_logger())
mtg_milp.set_milp_logger(get_logger())

########################################################################
# Setup done
########################################################################

wish_list_to_buy = read_card_list(data_path)
if not wish_list_to_buy:
    logger.error(color_msg([
        ("[ERROR] ", "d_red"),
        ("No cards found. Make sure you have a buy_list.txt file within the ./data folder... ", "rst"),
        ("Exiting", "b_yellow")]))

cards_name_list = []
# logger.info("\n".join([f"{q}x {color_msg([(str(name), 'b_yellow')])}" for name, q in card_list]))
total_qty = 0
for name, q in wish_list_to_buy:
    total_qty += q
    cards_name_list.append(name)
    logger.info(color_msg([
        ("[INFO] ", "b_yellow"),
        (str(q), 'b_cyan'),
        ("x ", 'rst'),
        (str(name), 'b_cyan')]))

# logger.info("Press any key to continue")
# x = input()
########################################################################
# Card info read
########################################################################

logger.info(color_msg([
    ("[INFO] ", "b_yellow"),
    ("Creating initial data frame: ", "rst"),
    ("good", "b_green")]))

########################################################################
# Creating Master data frame
########################################################################

# Create a directory to store the log files if it doesn't exist
os.makedirs(sites_path, exist_ok=True)
list_subfiles_with_paths = [f.path for f in os.scandir(sites_path)]

if use_previous_csv_results and list_subfiles_with_paths != []:
    logger.info(color_msg([
        ("[INFO] ", "b_yellow"),
        ("Reading csv files... ", "rst"),
        (str(list_subfiles_with_paths), "b_cyan"),
        (" good", "b_green")]))

    sites_results_df = read_csv(list_subfiles_with_paths)
    unique_cards_num = len(sites_results_df['Name'].unique())
    if unique_cards_num != len(cards_name_list):
        unique_names_set = set(sites_results_df['Name'].unique())
        card_names_set = set(cards_name_list)
        not_available_in_csv = card_names_set - unique_names_set
        more_in_csv = unique_names_set - card_names_set

        logger.debug(color_msg([
            ("[INFO] ", "b_yellow"),
            ("unique_names_in_df: ( ", "rst"),
            (f"{unique_names_set}", "b_cyan")]))
        logger.debug(color_msg([
            ("[INFO] ", "b_yellow"),
            ("card_list_set: ( ", "rst"),
            (f"{card_names_set}", "b_cyan")]))
        logger.debug(color_msg([
            ("[DEBUG] ", "b_blue"),
            ("Cards difference (not found in csv): ( ", "rst"),
            (f"{not_available_in_csv}", "b_cyan"),
            (")", "rst")]))
        logger.debug(color_msg([
            ("[DEBUG] ", "b_blue"),
            ("Cards difference (more in csv): ( ", "rst"),
            (f"{more_in_csv}", "b_cyan"),
            (")", "rst")]))

    logger.info(color_msg([
        ("[INFO] ", "b_yellow"),
        ("Sites read: ( ", "rst"),
        (f"{str(unique_cards_num)} / {str(len(wish_list_to_buy))}", "b_cyan"),
        (") unique cards found", "rst")]))
else:
    # Process every sites
    sites_results_df = fetch_all_card_details(
        cards_name_list, 
        special_site_flag, 
        save_all_results_to_csv)

########################################################################
# Check data integrity
########################################################################
if(sites_results_df is not None and sites_results_df.empty):
    logger.info(color_msg([
        ("[INFO] ", "b_yellow"),
        ("Got no results, sites_results_df is empty: ", "rst"),
        ("Exiting...", "b_red")]))
    exit()
sites_results_df = remove_entries_with_value(sites_results_df,'Quantity', 0)

# Extract all names and validate if they are prenent in the master dataframe
how_many = check_unmapped_cards(sites_results_df, cards_name_list)

# Check if some sites uses different naming convention for quality
check_unmapped_qualities(sites_results_df)

# Normalize the 'Quality' column using the mapping dictionary
sites_results_df['Quality'] = sites_results_df['Quality'].map(quality_mapping)

# Check if there are any unmapped quality values
unmapped_qualities = sites_results_df['Quality'].isna().sum()


message_type = "bad..." if unmapped_qualities != 0 else "good"
message_color = "b_red" if unmapped_qualities != 0 else "b_green"
logger.info(color_msg([
    ("[INFO] ", "d_yellow"),
    ("Numbers of for unmapped qualities[", "rst"),
    (str(unmapped_qualities), "b_green"),
    ("]: ", "rst"),
    (message_type, message_color)]))

# Apply the weights to the 'Price' column based on 'Quality'
sites_results_df['Weighted_Price'] = sites_results_df.apply(get_weighted_price, axis=1)

########################################################################
# Cover different use cases
########################################################################

# Separate data into foil and non-foil DataFrames
foil_df = sites_results_df[sites_results_df['Foil'].notnull() & (sites_results_df['Foil'] != '')]
non_foil_df = sites_results_df[sites_results_df['Foil'].isnull() | (sites_results_df['Foil'] == '')]

# Process foil and non-foil cards separately
logger.info(color_msg([
    ("[INFO] ", "d_yellow"),
    ("Processing stats x", "rst"),
    (f"{len(foil_df)}","d_cyan"),
    (" Foil[", "rst"),
    ("Yes", "b_green"),
    ("]: ", "rst")]))
if not foil_df.empty:
    unique_foil_cards = process_cards(foil_df)

logger.info(color_msg([
    ("[INFO] ", "d_yellow"),
    ("Processing stats x", "rst"),
    (f"{len(non_foil_df)}","d_cyan"),
    (" Foil[", "rst"),
    ("No", "b_red"),
    ("]: ", "rst")]))
if not non_foil_df.empty:
    unique_non_foil_cards = process_cards(non_foil_df)


########################################################################
# Process the results and find best solutions
########################################################################

# Concatenate results
processed_cards_df = pd.concat(
    [unique_foil_cards, unique_non_foil_cards], ignore_index=True)

# Sort by 'Name' and 'Weighted_Price' (or your preferred metric)
processed_cards_df = processed_cards_df.sort_values(by=['Name', 'Weighted_Price'])
sites_results_df = sites_results_df.sort_values(by=['Name', 'Weighted_Price'])

# Function to check availability in all_cards DataFrame
def is_available(row, cards_df):
    available_cards = cards_df[(cards_df['Name'] == row['Name']) & (
        cards_df['Quantity'] >= row['Quantity'])]
    return not available_cards.empty


# Assuming card_list is a list of dictionaries with 'Name' and 'Quantity' keys
available_cards_to_buy_df = pd.DataFrame(wish_list_to_buy, columns=['Name', 'Quantity'])

# Apply the availability check
available_cards_to_buy_df['IsAvailable'] = available_cards_to_buy_df.apply(
    is_available, axis=1, cards_df=sites_results_df)

# Filter out unavailable items
unavailable_cards_df = available_cards_to_buy_df[~available_cards_to_buy_df['IsAvailable']]
available_cards_to_buy_df = available_cards_to_buy_df[available_cards_to_buy_df['IsAvailable']]

available_cards_to_buy_df.drop(['IsAvailable'], axis=1, inplace=True)

logger.info(color_msg([
    ("[INFO] ", "d_yellow"),
    ("sites_results_df size: ", "rst"),
    (f"{str(len(sites_results_df))} ", "b_green"),
    ("available_cards_to_buy_df size: ", "rst"),
    (f"{str(len(available_cards_to_buy_df))} ", "b_green"),
    ("unavailable_cards_df size: ", "rst"),
    (f"{str(len(unavailable_cards_df))} ", "b_green")]))

os.makedirs(results_path, exist_ok=True)
save_dataframe_with_retry(sites_results_df, f"{results_path}/sites_results_df.csv")
save_dataframe_with_retry(processed_cards_df, f"{results_path}/processed_cards_df.csv")
save_dataframe_with_retry(available_cards_to_buy_df, f"{results_path}/available_cards_to_buy_df.csv")

if (milp_strat or hybrid_strat):
    standardized_cards_df = standardize_dataframe(sites_results_df)

    milp_plan_df, all_plans = mtg_milp.run_pulp(standardized_cards_df, available_cards_to_buy_df, min_store, find_min_store)
    card_dicts = [card.to_dict() for card in milp_plan_df["Original_Card"]]
    df = pd.DataFrame(card_dicts)
    save_dataframe_with_retry(df, f"{results_path}/milp_plan_df.csv")

    for plan in all_plans:
        card_dicts = [card.to_dict() for card in plan['sorted_results_df']["Original_Card"]]
        df = pd.DataFrame(card_dicts)
        save_dataframe_with_retry(df, f"{results_path}/milp_plan_with_{plan['Number_store']}_stores.csv")
    
if (nsga_algo_strat or hybrid_strat):
    logger.info(color_msg([
        ("Using [", "rst"),
        ("NGSA Algorythm", "b_green"),
        ("] to find best combination...", "rst")]))

    standardized_cards_df = standardize_dataframe(sites_results_df)

    # Run the optimization algorithm
    if hybrid_strat:
        # Create a unique identifier in card_details_df
        standardized_cards_df['Identifier'] = standardized_cards_df.apply(lambda row: f"{row['Name']}_{row['Site']}_{row['Price']}", axis=1)

        # Create a mapping from the unique identifier to index
        identifier_to_index = {identifier: idx for idx, identifier in standardized_cards_df['Identifier'].items()}

        # Convert MILP results to milp_solution
        milp_solution = []
        for _, row in milp_plan_df.iterrows():
            # row is a Series, so you can access its elements using ['ColumnName']
            identifier = f"{row['Card']}_{row['Store']}_{row['Price']}"
            if identifier in identifier_to_index:
                idx = identifier_to_index[identifier]
                milp_solution.append(idx)
            else:
                print(f"Combination {identifier} not found in card_details_df.")


        # Drop the 'Identifier' column as it's no longer needed
        standardized_cards_df = standardized_cards_df.drop(columns=['Identifier'])

        # Now you can use milp_solution as an initializer for NSGA-II
        pareto_front = mtg_deap.run_nsga_ii(standardized_cards_df, available_cards_to_buy_df, milp_solution=milp_solution)

        # Run NSGA-II with the MILP solution as part of the initial population
        pareto_front = mtg_deap.run_nsga_ii(standardized_cards_df, available_cards_to_buy_df, milp_solution=milp_solution)
    else:
        # Run NSGA-II without the MILP solution
        pareto_front = mtg_deap.run_nsga_ii(standardized_cards_df, available_cards_to_buy_df)

    # Process the Pareto front
    best_solution = None
    best_score = float('inf')

    # Adjusted weights
    weight_cost = 0.45
    weight_quality = 0.3  # Adjust as needed
    weight_availability = 0.15  # Adjust as needed
    weight_num_stores = 0.1  # Adjust as needed

    def normalize_cost(cost):
        return (cost - 100) / (900)  # Assuming costs range from $100 to $1000

    def normalize_num_stores(num_stores):
        return (num_stores - 1) / (19)  # Assuming store count ranges from 1 to 20

    for solution in pareto_front:
        cost, quality, availability, num_stores = solution.fitness.values

        normalized_cost = normalize_cost(cost)
        normalized_num_stores = normalize_num_stores(num_stores)
        # Composite score calculation
        composite_score = (weight_cost * normalized_cost +
                   weight_quality * quality +
                   weight_availability * availability +
                   weight_num_stores * normalized_num_stores)
        
        if composite_score < best_score:
            logger.info(color_msg([("A new \"best solution\" was found: ", "rst")]))
            logger.info(color_msg([("cost: ", "b_yellow"),(f"{str(weight_cost * cost)} ({cost}) ", "b_green")]))
            logger.info(color_msg([("quality: ", "b_yellow"),(f"{str(weight_quality * (1/quality))} ({quality})", "b_green")]))
            logger.info(color_msg([("availability: ", "b_yellow"),(f"{str(weight_availability * (availability) )} ({availability})", "b_green")]))
            logger.info(color_msg([("num_stores: ", "b_yellow"),(f"{str(weight_num_stores * num_stores)} ({num_stores})", "b_green")]))
            logger.info(color_msg([("composite_score vs old composite_score: ", "b_yellow"),(f"{str(composite_score)} vs {str(best_score)}", "b_green")]))
            
            best_score = composite_score
            best_solution = solution

    # Extract the purchasing plan from the best solution
    if best_solution:
        # Map the solution back to your card_details_df to determine the purchasing plan
        purchasing_plan = mtg_deap.extract_purchasing_plan(
            best_solution, standardized_cards_df, available_cards_to_buy_df)

        # Convert the list of dictionaries into a DataFrame
        purchasing_plan_df = pd.DataFrame(purchasing_plan)

        logger.info(color_msg([
            ("Was a \"best solution\" found: ", "rst"),
            ("Yes", "b_green"),
            (f" ({len(purchasing_plan)} / {len(available_cards_to_buy_df)})", "rst")]))
        # Save the purchasing plan DataFrame to a CSV file
        save_dataframe_with_retry(
            purchasing_plan_df, f"{results_path}/purchasing_plan_df.csv")
        display_purchasing_plan(purchasing_plan_df)
    else:
        logger.info(color_msg([
            ("Was a \"best solution\" found: ", "rst"),
            ("No", "b_red")]))
elif best_site_strat:
    logger.info(color_msg([
        ("Using [", "rst"),
        ("Weight Algorythm", "b_green"),
        ("] to find best combination...", "rst")]))

    best_sites, total_cost, cards_not_found = find_best_sites(
        processed_cards_df, available_cards_to_buy_df)

    # Extracting the best_sites information for better formatting
    sites_info = []
    for site_name, site_df in best_sites:
        sites_info.append(f"\nSite: {site_name}\n{site_df}")

    # Using the formatted info in the logger message
    logger.info(color_msg([
        ("Best sites to order from: \n", "rst"),
        ("\n".join(sites_info), "b_green"),
        ("\nTotal cost: ", "rst"),
        (str(total_cost), "b_green")]))

    if cards_not_found:
        logger.info(color_msg([
            ("Cards not found are : \n", "rst"),
            (str(cards_not_found), "b_yellow")]))

    # check_and_save_strat(best_sites, "best_sites")
    # check_and_save_strat(cards_not_found,"cards_not_found")

# Drop duplicates, keeping the first (cheapest) option per card name
unique_cards = processed_cards_df.drop_duplicates(subset='Name', keep='first')

# Save the result to file
save_the_data(unique_cards, results_path)
