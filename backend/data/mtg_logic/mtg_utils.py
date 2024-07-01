import os
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from data.mtg_logic.mtg_logger import *
from data.mtg_logic.mtg_scrapper import *
from data.mtg_logic.mtg_utils import *

# Create a dictionary to map qualities to weights
quality_weights = {'NM': 1, 'LP': 1.3, 'MP': 1.7, 'HP': 2.5, 'DMG':999999}

# Create a mapping dictionary for quality normalization
quality_mapping = {
    'NM': 'NM',
    'Brand New':'NM',
    'New':'NM',
    'Stamped':'NM',
    'NM-Mint': 'NM',
    'Mint/Near-Mint': 'NM',
    'Near Mint':'NM',
    'Hero Deal':'LP',
    'Slightly Played': 'LP',
    'Light Play': 'LP',
    'Lightly Played': 'LP',
    'LP': 'LP',
    'PL/MP': 'MP',
    'Moderate Play': 'MP',
    'Moderatly Play': 'MP',
    'Moderatly Played': 'MP',
    'Moderately Played': 'MP',
    'MP': 'MP',
    'PL': 'MP',
    'Heavy Played': 'HP',
    'Heavily Played': 'HP',
    'Heavy Play': 'HP',
    'HP': 'HP',
    'DMG': 'DMG',
    'Dmg': 'DMG',
    'Damaged': 'DMG'
    # Add more quality mappings as needed
}

logger = None

def set_utils_logger(new_logger):
    global logger
    logger = new_logger

def calculate_cost_and_fulfillment(site_inventory_df, unfulfilled_items_df):
    """
    Calculate the total cost to fulfill as many unfulfilled items as possible from this site,
    and return the items that would be fulfilled.

    :param site_inventory_df: DataFrame of the site's inventory
    :param unfulfilled_items_df: DataFrame of the items still needed
    :return: Total cost from this site, DataFrame of items that would be fulfilled
    """
    cost = 0
    fulfillment = []
    
    for index, item in unfulfilled_items_df.iterrows():
        # Find the corresponding item in the site's inventory
        site_item = site_inventory_df[
            (site_inventory_df['Name'] == item['Name']) &
            (site_inventory_df['Quantity'] >= item['Quantity'])
        ]
        
        # If the item is found and is cheaper than our remaining item, add its price to the cost
        if not site_item.empty:
            cost += site_item['Price'].min() * item['Quantity']
            fulfillment.append(item)
            
    return cost, pd.DataFrame(fulfillment, columns=['Name', 'Quantity'])
   
#@profile
def calculate_stats(group):
    card_name = group.name 
    mean_price = group['Weighted_Price'].mean()
    min_price = group['Weighted_Price'].min()
    max_price = group['Weighted_Price'].max()
    std_price = group['Weighted_Price'].std()
    idx_min = group['Weighted_Price'].idxmin()
    
    logger.info(color_msg([
        ("[INFO] ", "d_yellow"),
        ("Stats - [", "rst"),
        (str(card_name), "b_cyan"),
        ("] mean: ", "rst"),
        ("{:.2f}".format(mean_price), "b_green"),
        (", std: ", "rst"),
        ("{:.2f}".format(std_price), "b_green"),
        (", min: ", "rst"),
        ("{:.2f}".format(min_price), "b_green"),
        (", max: ", "rst"),
        ("{:.2f}".format(max_price), "b_green"),
        (", idx_min: ", "rst"),
        (str(idx_min), "b_green")]))
    
    return pd.Series([mean_price, std_price, idx_min], index=['mean_price', 'std_price', 'idx_min'])

def check_dataframe(df):
    logger.debug(color_msg([
        ("[INFO] ", "d_yellow"),
        ("Checking dataframe...\n", "rst")]))
    
    print(df.isna().sum())
    print(df.dtypes)
    print(df['Name'].unique())
    print(df.duplicated().sum())

def check_unmapped_cards(sites_results_df, cards_name_list):
   # Extract all names and split them by ' // ', creating a flat list of all names
    all_names_in_df = [name.strip() for name in sites_results_df['Name']]

    # Find the items in card_names that are not in master_df
    not_in_dataframe = [item for item in cards_name_list if item not in all_names_in_df]
    nbr = len(not_in_dataframe) 
    if nbr > 0:
            logger.warning(color_msg([
                ("[Warning] ", "d_yellow"),
                ("Some cards not in dataframe[", "rst"),
                (nbr, "b_cyan"),
                ("]...", "rst")]))
            for item in not_in_dataframe:
                logger.info(color_msg([
                ("     --> ", "d_yellow"),
                (str(item), "d_cyan")]))
    return nbr

def check_unmapped_qualities(master_df):

    # Assuming master_df is your DataFrame
    unique_qualities = master_df['Quality'].unique()

    # Find qualities in your DataFrame that are not in your mapping dictionary
    unmapped_qualities_before_mapping = [q for q in unique_qualities if q not in quality_mapping]

    # Log/Print unmapped qualities
    if unmapped_qualities_before_mapping:
        logger.warning(color_msg([
            ("The following qualities were not found in the mapping dictionary: ", "rst"),
            (', '.join(unmapped_qualities_before_mapping), "b_yellow")
        ]))
        
        # Log/Print DataFrame entries with unmapped qualities
        for unmapped_quality in unmapped_qualities_before_mapping:
            unmapped_entries = master_df[master_df['Quality'] == unmapped_quality]
            logger.warning(color_msg([
                ("Warning: ", "d_yellow"),
                ("Entries with unmapped quality [", "rst"),
                (str(unmapped_quality), "b_cyan"),
                ("]:\n", "rst"),
                (str(unmapped_entries),"rst")]))
            
            # Ask user for the correct mapping
            new_mapping = input(f"Enter the correct mapping for quality '{unmapped_quality}': ")

            if new_mapping:  # Check if user provided a non-empty string
                # Update the quality_mapping dictionary
                quality_mapping[unmapped_quality] = new_mapping

                # Update the 'Quality' column in the DataFrame
                master_df.loc[master_df['Quality'] == unmapped_quality, 'Quality'] = new_mapping

def display_purchasing_plan(purchasing_plan):
    
    # Group by Site and Name, and aggregate the Quantity and Price
    grouped_plan = purchasing_plan.groupby(['Site', 'Name']).agg({'Quantity': 'sum', 'Price': 'sum',
        'Quality': lambda x: ', '.join(x.unique())  # Join unique quality values
        }).reset_index()

    # Display the plan
    for index, row in grouped_plan.iterrows():
        message = [
            ("[INFO] ", "d_yellow"),
            ("Buy ", "rst"),
            (f"{row['Quantity']}x ", "b_green"),
            (f"{row['Name']} ", "b_cyan"),
            ("from ", "rst"),
            (f"{row['Site']} ", "b_green"),
            ("with quality ", "rst"),
            (f"{row['Quality']} ", "b_cyan"),
            ("at a total price of ", "rst"),
            (f"${row['Price']:.2f}", "b_green")
        ]
        logger.info(color_msg(message))

    # Calculate and display the total cost
    total_cost = grouped_plan['Price'].sum()
    total_cost_message = [
        ("[INFO] ", "d_yellow"),
        ("Total cost of the purchasing plan: ", "rst"),
        (f"${total_cost:.2f}", "b_green")
    ]
    logger.info(color_msg(total_cost_message))

def fetch_all_card_details(card_names, special_site_flag=True, save_all_research=True):
    """
    Fetches card details from all the provided sites.

    Args:
    - card_names (list): List of card names to search for.
    - special_site_flag (bool): Flag indicating whether to consider sites with '--' in front.

    Returns:
    - DataFrame: A DataFrame containing card details from all sites.
    """
    
    # The following functions and variables are from your existing code
    # They need to be imported or defined here for this function to work
    # read_site_list, extract_domain, process_sites

    sites = read_site_list(special_site_flag)
    master_df = pd.DataFrame(columns=[
        'Site',
        'Name',
        'Edition',
        'Version',
        'Foil',
        'Quality',
        'Language',
        'Quantity',
        'Price' 
    ])

    # Determine the number of workers based on your system and requirements
    workers = min(30, len(sites))
    
    dash_line_message = "{:-<52}".format("")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit the process_store function for each store
        future_to_site = {executor.submit(process_sites, site, card_names, strategy): \
                          (site, strategy) for site, strategy in sites}

    for future in as_completed(future_to_site):
        site, strategy = future_to_site[future]  # Unpack the tuple
        try:
            cards_df = future.result()
            bad = False
            if cards_df is None or cards_df.empty:
                bad = True
            # Process the result for the store
            domain = extract_domain(site)

            # Creating a mix of colored and non-colored text
            logger.info(color_msg([(str(dash_line_message), "b_magenta")]))

            mixed_message = color_msg(
                [("Results for site:", "rst"), (domain, "b_cyan")])
            mixed_msg_pad(mixed_message)

            message_type = "bad..." if bad == True else "good"
            message_color = "b_red" if bad == True  else "b_green"

            mixed_message = color_msg(
                [("Search is complete: ", "rst"),  (message_type, message_color)])
            mixed_msg_pad(mixed_message)

            logger.info(color_msg([(str(dash_line_message), "b_magenta")]))

            if (cards_df is not None and 
                    not cards_df.empty):
                if master_df.empty:
                    # If master_df is empty, assign cards_df directly
                    master_df = cards_df.copy()
                else:
                    # Concatenate only if master_df is not empty
                    master_df = pd.concat(
                        [master_df, cards_df], ignore_index=True)
                mixed_message = color_msg(
                    [("Number of card found: ", "rst"), (str(len(cards_df)), "d_green")])
                mixed_msg_pad(mixed_message)

                mixed_message = color_msg([("Extraction complete: ", "rst"), (str(
                    len(cards_df)), "d_green"), (" cards found !", "rst")])
                mixed_msg_pad(mixed_message)

                mixed_message = color_msg(
                    [("Concatenation complete: ", "rst"), ("good", "d_green")])
                mixed_msg_pad(mixed_message)

                if save_all_research:
                    site_filename = f'sites\{str(domain)}.csv'
                    mixed_message = color_msg(
                        [("Saving to: ", "rst"), (site_filename, "d_green")])
                    mixed_msg_pad(mixed_message)
                    save_dataframe_with_retry(cards_df, site_filename)
            else:
                mixed_message = color_msg(
                    [("Concatenation Incomplete: ", "rst"), ("Bad...", "d_red")])
                mixed_msg_pad(mixed_message)

                logger.error(color_msg(
                    [(str(domain), "b_cyan"), (" Error: all methods failed... ", "b_red")]))
            logger.info(color_msg([(str(dash_line_message), "b_magenta")]))
        except Exception:
            stack_trace = traceback.format_exc()
            logger.error(color_msg([
                (str(site), "b_cyan"),
                (f" generated an exception: {stack_trace}", "b_red")]))
    return master_df
    
def find_best_sites(master_df, unfulfilled_items_df):
    best_sites = []  # This will store tuples (site_name, fulfilled_cards_df)
    total_cost = 0
    cards_not_found = {}
    iteration = 0  # Add an iteration counter for debugging

    # Handling uniquely available cards before the while loop
    unique_cards = unfulfilled_items_df[unfulfilled_items_df['Name'].isin(
        master_df.groupby('Name')['Site'].filter(lambda x: len(x.unique()) == 1)
    )]

    for card_name, card_group in unique_cards.groupby('Name'):
        site = card_group['Site'].iloc[0]
        card_fulfillment_df = master_df[(master_df['Site'] == site) & (master_df['Name'] == card_name)]
        total_cost += card_fulfillment_df['Price'].sum()
        best_sites.append((site, card_fulfillment_df))

    # Update unfulfilled_items_df
    unfulfilled_items_df = unfulfilled_items_df[~unfulfilled_items_df['Name'].isin(unique_cards['Name'])]

    while not unfulfilled_items_df.empty:
        logger.info(f"Start of iteration {iteration}. Number of unfulfilled cards: {len(unfulfilled_items_df)}")

        best_score = float('-inf')
        best_site = None
        best_site_fulfillment = None

        for site_name, site_inventory_df in master_df.groupby('Site'):
            site_fulfillment_df = site_inventory_df[site_inventory_df['Name'].isin(unfulfilled_items_df['Name'])]
            num_cards_fulfilled_by_site = len(site_fulfillment_df)
            site_total_cost = site_fulfillment_df['Price'].sum()

            if site_total_cost > 0:
                score = num_cards_fulfilled_by_site / site_total_cost
            else:
                logger.info(f"Site {site_name} has zero total cost. Assigning score as -inf.")
                score = float('-inf')  # Assign a default score for zero cost


            if score > best_score:
                best_score = score
                best_site = site_name
                best_site_fulfillment = site_fulfillment_df

        if not best_site:
            logger.warning("Warning: no site can fulfill any more cards, break")
            break

        logger.info(f"End of Bulk Fulfillment step: Best site is {best_site} fulfilling {len(best_site_fulfillment)} cards.")

        site_cards_df = master_df[(master_df['Site'] == best_site) & (master_df['Name'].isin(unfulfilled_items_df['Name']))]

        # Cost Optimization: Select all cards that are within 10% of the minimum price
        threshold = 1.10  # 10% more than the minimum price
        min_price = site_cards_df['Price'].min()
        cost_optimized_cards = site_cards_df[site_cards_df['Price'] <= min_price * threshold]

        total_cost += cost_optimized_cards['Price'].sum()
        best_sites.append((best_site, cost_optimized_cards))
        unfulfilled_items_df = unfulfilled_items_df[~unfulfilled_items_df['Name'].isin(cost_optimized_cards['Name'])]

        logger.info(f"Unfulfilled cards after update: {unfulfilled_items_df['Name'].tolist()}")
        logger.info(f"End of iteration {iteration}. Number of unfulfilled cards: {len(unfulfilled_items_df)}")
        iteration += 1
        if iteration > 100:
            logger.warning("Reached maximum iterations. Breaking out of the loop.")
            break

    for _, card_row in unfulfilled_items_df.iterrows():
        card_name = card_row['Name']
        cards_not_found[card_name] = "Not available in any store"
    
    return best_sites, total_cost, cards_not_found

def get_number_of_cards(df):
    try:
        # Check if DataFrame is not None and has 'Quantity' column
        if df is not None and 'Quantity' in df.columns:
            return df['Quantity']
        else:
            return 0
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return 0
    
#@profile
def get_weighted_price(row):
    try:
        return row['Price'] * quality_weights[row['Quality']]
    except KeyError:
        # Set a default value if the quality is not found
        logger.warning(color_msg([
            ("Quality: ","rst"),
            (str(row["Quality"]), "d_cyan"),
            (f" not found and need updating: \n{row}","rst")]))
        return row['Price'] * 1.0
    except (Exception) as e:
        logger.exception("An error occurred")
        logger.error(color_msg([
            ("Error: ","d_red"),
            (f" Price: ", "rst"),
            (str(row["Price"]), "d_cyan"),
            (" Quality: ", "rst"),
            (str(row["Quality"]), "d_cyan"),
            (" quality_weight: ", "rst"),
            (str(quality_weights[row["Quality"]]), "d_cyan")]))
   
def print_df(df):

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)

    logger.info(f'Printing dataframe:\n\n{df}')

    pd.reset_option('display.max_rows')
    pd.reset_option('display.max_columns')
    pd.reset_option('display.width')
    pd.reset_option('display.max_colwidth')

#@profile
def prioritize_better_quality(grouped):
# A function to compare cards and prioritize better quality cards
    price_pct_threshold = 0.85
    cards = []
    for _, group in grouped:
        group = group.reset_index(drop=True)
        best_quality_card = group.iloc[0]
        for i in range(1, len(group)):
            card = group.iloc[i]
            if (
                (card['Weighted_Price'] < (best_quality_card['Weighted_Price'] * price_pct_threshold)) 
                and (card['Quantity'] > 0)):
                best_quality_card = card
            else:
                break
        cards.append(best_quality_card)
    return pd.DataFrame(cards)
    
def process_cards(df):
    # Sort by Weighted_Price for initial processing
    df = df.sort_values(by='Weighted_Price', ascending=True)
    # Group by Name and calculate stats
    grouped = df.groupby('Name')
    stats = grouped.apply(calculate_stats).reset_index()
    # Merge the stats back into the original DataFrame
    df = pd.merge(df, stats, on='Name', how='left')
    # Group by Name again and prioritize better quality
    grouped = df.groupby('Name')
    unique_cards = prioritize_better_quality(grouped)
    # Sort the resulting DataFrame by Name
    unique_cards = unique_cards.sort_values(by='Name', ascending=True)

    return unique_cards

def read_card_list(data_path):
    logger.info(color_msg([
        ("Reading buy list: ", "rst"),
        (" good", "b_green")]))
    
    # Define a list of card names to search for
    with open(f"{data_path}/buy_list.txt", "r") as f:
        card_names = f.readlines()    
    
    # Extract quantity and card name
    total_qty = 0
    card_list = []
    for line in card_names:
        # Regular expression to match quantity
        # match = re.match(r'(?:(\d+)x?\s)?(.+)', line.strip().split(" // ")[0])
        match = re.match(r'(?:(\d+)x?\s)?(.+)', line.strip())
        if match:
            quantity, card_name = match.groups()
            # If quantity is not provided, default to 1
            quantity = int(quantity) if quantity is not None else 1
            total_qty += quantity
            card_list.append((card_name.strip(), quantity))
    
    
    message_type = " bad..." if len(card_names) != total_qty else " good"
    message_color = "b_red" if len(card_names) != total_qty else "b_green"
    logger.info(color_msg([
        (f"{str(len(card_names))}/{total_qty}", "d_cyan"),
        (" unique card names found: ", "rst"),
        (message_type, message_color)]))
    logger.debug(f'--------------------')
    logger.debug(f'cards are: \n%s', "\n".join([f"{q}x {name}" for name, q in card_list]))
    logger.debug(f'--------------------')
    return card_list

def read_csv(file_paths):
    dataframes = [pd.read_csv(file) for file in file_paths]
    return pd.concat(dataframes, ignore_index=True)

def read_site_list(special_site_flag):
    logger.info(color_msg([
        ("[INFO] ", "b_yellow"),
        ("Reading site list: ", "rst"),
        (" good", "b_green")]))
            
    # Define a list of CrystalCommerce sites to search
    with open(r'./data/site_list.txt', "r") as f:
        sites = []
        for line in f.readlines():
            site_info = line.strip().split(',')  # Split line into site and strategy
            site = site_info[0].strip()  # Extract site URL
            strategy = site_info[1].strip() if len(site_info) > 1 else 1  # Default strategy to '1' if not specified
            sites.append((site, int(strategy)))  # Append tuple of (site, strategy)
 
    # Categorize sites based on prefix
    regular_sites = [(site, strategy) for site, strategy in sites if (not site.startswith('--') and not site.startswith('xx'))]
    special_sites = [(site[2:], strategy) for site, strategy in sites if site.startswith('--')]
    not_working_sites = [(site, strategy) for site, strategy in sites if site.startswith('xx')]
    
    # Optionally include 'special' sites based on flag
    considered_sites = regular_sites + special_sites if special_site_flag else regular_sites
    
    logger.info(color_msg([
        ("[INFO] ", "b_yellow"),
        (str(len(considered_sites)), "d_cyan"),
        (" sites found: ", "rst"),
        (" good", "b_green")]))
    logger.debug(f'--------------------')
    logger.debug('sites are: \n%s', "\n".join([f'{site}, {strategy}' for site, strategy in considered_sites]))
    logger.debug(f'--------------------')
    return considered_sites

def remove_entries_with_value(df, column, value):
    df = df[df[column] != value]
    return df

#@profile
def save_dataframe_with_retry(container, filename):
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        # Check if the file exists
        if os.path.exists(filename):
            try:
                # Try to open the file in write mode to check if it's accessible
                with open(filename, "w") as test_file:
                    pass  # If successful, do nothing

                # If the file is accessible, save the DataFrame to it
                container.to_csv(filename, index=False)
                logger.info(color_msg([
                    ("[INFO] ", "d_yellow"),
                    ("Data saved ", "rst"),
                    ("successfully", "b_green"),
                    (" to ", "rst"),
                    (str(filename), "d_cyan")]))
                
                return  # Exit the function after successful save
            except PermissionError:
                # If the file is not accessible, prompt the user to close it
                logger.error(color_msg([
                    ("Please close the file: ", "rst"),
                    (str(filename), "d_red"),
                    (" and try again.", "rst")]))
        else:
            # If the file does not exist, save the DataFrame to it
            container.to_csv(filename, index=False)
            logger.info(color_msg([
                ("[INFO] ", "d_yellow"),
                ("Data saved ", "rst"),
                ("successfully", "b_green"),
                (" to ", "rst"),
                (str(filename), "d_cyan")]))
            return  # Exit the function after successful save

        retry_count += 1
        if retry_count < max_retries:
            choice = input("Do you want to (C)ancel, choose a (D)ifferent name, or (R)etry? ").strip().lower()
            if choice == "c":
                logger.info(color_msg([
                    ("Operation cancelled.", "b_cyan")]))
                return  # Exit the function if canceled
            elif choice == "d":
                new_filename = input("Enter a different filename: ").strip()
                if new_filename:
                    filename = new_filename
            # Retry if neither "C" nor "D" is chosen

    # If max_retries are reached, append a number to the filename
    filename_base, file_extension = os.path.splitext(filename)
    new_filename = f'{filename_base}_{retry_count}{file_extension}'
    container.to_csv(new_filename, index=False)
    logger.info(color_msg([
        ("Data saved ", "rst"),
        ("successfully", "b_green"),
        (" as ", "rst"),
        (str(new_filename), "b_cyan"),
        ("after ","rst"),
        (str(max_retries), "b_yellow"),
        ("retries.", "rst")]))

#@profile 
def save_the_data(unique_cards, results_path):

    # Group by 'Site' and count the number of unique cards per site
    unique_cards_per_site = unique_cards.groupby('Site').size().reset_index(name='Count')

    # Sort the sites by the number of unique cards in descending order
    unique_cards_per_site = unique_cards_per_site.sort_values(by='Count', ascending=False)

    # Calculate the minimum number of sites to order from
    min_sites = 0
    total_unique_cards = len(unique_cards)
    
    logger.debug(color_msg([
        ("Unique cards [", "rst"),
        (str(total_unique_cards), "b_cyan"),
        ("] found are: \n\n", "rst"),
        (str(unique_cards), "b_cyan")]))
    cards_accumulated = 0

    for _, row in unique_cards_per_site.iterrows():
        min_sites += 1
        cards_accumulated += row['Count']
        if cards_accumulated >= total_unique_cards:
            break

    # logger.info(color_msg([
    #     ("Minimum number of different sites to order from: ", "rst"),
    #     (str(min_sites), "b_cyan"),
    #     (" good", "b_green")]))

    # Save the final unique cards DataFrame to a CSV file    
    save_dataframe_with_retry(unique_cards, f"{results_path}/unique_cards.csv")

    # Save the unique cards per site DataFrame to a CSV file
    save_dataframe_with_retry(unique_cards_per_site, f"{results_path}/unique_cards_per_site.csv")

    logger.info(color_msg([
        ("Data saved to CSV files: ", "rst"),
        (" good", "b_green")]))

def should_consider_site(site_name, flag):
    """
    Check if a site should be considered based on its name and a flag.
    
    Parameters:
    - site_name (str): The name of the site.
    - flag (bool): A flag indicating whether to consider certain sites.
    
    Returns:
    - bool: True if the site should be considered, False otherwise.
    """
    return site_name.startswith('--') and flag

# Prepare card details DataFrame
def standardize_dataframe(all_cards_df):
    card_details_df = all_cards_df.copy()
    card_details_df['Foil'] = card_details_df['Foil'].apply(
        lambda x: 1 if x else 0)
    return card_details_df


def update_unfulfilled_items(unfulfilled_items_df, fulfilled_items_df):
    """
    Update `unfulfilled_items_df` to remove items in `fulfilled_items_df`.

    :param unfulfilled_items_df: DataFrame of items still needed
    :param fulfilled_items_df: DataFrame of items to be removed
    :return: Updated DataFrame of items still needed
    """
    # return unfulfilled_items_df[~unfulfilled_items_df['Name'].isin(fulfilled_items_df['Name'])]
    #logger.debug(f"Attempting to remove:\n {fulfilled_items_df}")
    #logger.debug(f"\n From :\n {unfulfilled_items_df}")
    
    # Step 1 & 2: Check if names in `unfulfilled_items_df` are in `fulfilled_items_df`
    name_is_in_fulfilled = unfulfilled_items_df['Name'].isin(fulfilled_items_df['Name'])
    #logger.debug(f"Step 1 & 2: Check if names:\n {name_is_in_fulfilled}")
    
    # Step 3: Negate the condition
    name_is_not_in_fulfilled = ~name_is_in_fulfilled
    #logger.debug(f"Step 3: Negate the condition:\n {name_is_not_in_fulfilled}")
    
    # Step 4: Apply the condition to `unfulfilled_items_df` and assign it to `updated_df`
    updated_df = unfulfilled_items_df[name_is_not_in_fulfilled]
    #logger.debug(f"Step 4: Apply the condition:\n {updated_df}")
    
    updated_df = unfulfilled_items_df[~unfulfilled_items_df['Name'].isin(fulfilled_items_df['Name'])]
    #logger.debug(f"Items after removal:\n {updated_df}")
    return updated_df