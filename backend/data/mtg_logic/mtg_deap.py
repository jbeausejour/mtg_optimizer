import datetime
from deap import base, creator, tools
import random
from functools import partial
import pandas as pd
from mtg_logger import *

logger = None

def set_deap_logger(new_logger):
    global logger
    logger = new_logger

creator.create("FitnessMulti", base.Fitness, weights=(-1.0, 1.0, 1.0, -1.0))
creator.create("Individual", list, fitness=creator.FitnessMulti)

def custom_crossover(ind1, ind2):
    for i in range(len(ind1)):
        if random.random() < 0.5:
            ind1[i], ind2[i] = ind2[i], ind1[i]
    return ind1, ind2

def custom_mutation(individual, card_details_df, buylist, indpb=0.05):
    for i in range(len(individual)):
        if random.random() < indpb:
            mutation_index = random.randrange(len(individual))
            card_name = buylist.iloc[mutation_index]['Name']
            available_options = card_details_df[card_details_df['Name'] == card_name]
            if not available_options.empty:
                selected_option = available_options.sample(n=1)
                individual[mutation_index] = selected_option.index.item()
    return individual,

def evaluate_solution_wrapper(card_details_df, buylist):
    def evaluate_solution(individual):
        total_cost = 0
        total_quality_score = 0
        stores = set()
        card_counters = {row['Name']: row['Quantity'] for _, row in buylist.iterrows()}
        card_availability = {row['Name']: 0 for _, row in buylist.iterrows()}
        language_penalty = 999
        quality_weights = {'NM': 9, 'LP': 7, 'MP': 3, 'HP': 1, 'DMG': 0}
        missing_cards_penalty = 0
        store_diversity_penalty = 0
        all_cards_present = all(card_counters[getattr(card_row, 'Name')] > 0 for card_row in card_details_df.itertuples())
        if not all_cards_present:
            return (float('inf'),)
        for idx in individual:
            if idx not in card_details_df.index:
                print(f"Invalid index: {idx}")
                continue
            card_row = card_details_df.loc[idx]
            card_name = card_row['Name']
            if card_counters[card_name] > 0:
                card_counters[card_name] -= 1
                card_availability[card_name] += card_row['Quantity']
                card_price = card_row['Price']
                if card_row['Language'] != 'English':
                    card_price *= language_penalty
                total_cost += card_price
                total_quality_score += quality_weights.get(card_row['Quality'], 0)
                stores.add(card_row['Site'])
        missing_cards_penalty = 10000 * sum(count for count in card_counters.values() if count > 0)
        store_diversity_penalty = 100 * (len(stores) - 1)
        card_quality = total_quality_score / len(individual) if individual else 0
        all_available = all(card_availability[name] >= qty for name, qty in card_counters.items())
        availability_score = 1 if all_available else 0
        num_stores = len(stores)
        return (total_cost + missing_cards_penalty + store_diversity_penalty, -card_quality, -availability_score, num_stores)
    return evaluate_solution

def initialize_individual(card_details_df, buylist):
    individual = []
    for _, card in buylist.iterrows():
        available_options = card_details_df[card_details_df['Name'] == card['Name']]
        if not available_options.empty:
            selected_option = available_options.sample(n=1)
            individual.append(selected_option.index.item())
        else:
            print(f"Card {card['Name']} not available in any store!")
    return creator.Individual(individual)

def initialize_population(n, card_details_df, buylist):
    return [initialize_individual(card_details_df, buylist) for _ in range(n)]

def initialize_population_with_milp(n, card_details_df, buylist, milp_solution):
    population = [initialize_individual(card_details_df, buylist) for _ in range(n-1)]
    milp_individual = milp_solution_to_individual(milp_solution)
    population.insert(0, milp_individual)
    return population

def initialize_toolbox(card_details_df, buylist):
    toolbox = base.Toolbox()
    toolbox.register("mate", custom_crossover)
    toolbox.register("select", tools.selNSGA2)
    toolbox.register("attr_idx", random.randint, 0, len(card_details_df) - 1)
    toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_idx, n=sum(buylist['Quantity']))
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    custom_mutation_with_args = partial(custom_mutation, card_details_df=card_details_df, buylist=buylist)
    toolbox.register("mutate", custom_mutation_with_args)
    evaluate_function = evaluate_solution_wrapper(card_details_df, buylist)
    toolbox.register("evaluate", evaluate_function)
    return toolbox

def milp_solution_to_individual(milp_solution):
    return creator.Individual(milp_solution)

def run_nsga_ii(card_details_df, buylist, milp_solution=None):
    toolbox =initialize_toolbox(card_details_df, buylist)
    NGEN = 1000
    MU = 3000
    CXPB = 0.5
    MUTPB = 0.2
    ELITISM_SIZE = int(0.1 * MU)
    if milp_solution:
        milp_individual = milp_solution_to_individual(milp_solution)
        pop = initialize_population_with_milp(MU, card_details_df, buylist, milp_individual)
    else:
        pop = toolbox.population_custom(n=MU)
    fitnesses = map(toolbox.evaluate, pop)
    for ind, fit in zip(pop, fitnesses):
        ind.fitness.values = fit
    pareto_front = tools.ParetoFront()
    convergence_threshold = 0.01
    num_generations_threshold = 10
    best_fitness_so_far = float('inf')
    generations_without_improvement = 0
    for gen in range(NGEN):
        last_time = datetime.datetime.now()
        offspring = toolbox.select(pop, len(pop))
        offspring = list(map(toolbox.clone, offspring))
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < CXPB:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values
        for mutant in offspring:
            if random.random() < MUTPB:
                toolbox.mutate(mutant)
                del mutant.fitness.values
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit
        top_individuals = tools.selBest(pop, ELITISM_SIZE)
        offspring.extend(top_individuals)
        pop[:] = offspring
        pareto_front.update(pop)
        current_time = datetime.datetime.now()
        delta_time = current_time - last_time
        delta_time_str = str(delta_time)
        logger.warning(color_msg([("[INFOS] ", "d_yellow"), ("Ran gen:", "rst"), (str(gen), "d_cyan"), (" T[", "rst"), (delta_time_str, "d_cyan"), ("]", "rst")]))
        avg_fitness = sum(ind.fitness.values[0] for ind in pop) / len(pop)
        best_fitness = tools.selBest(pop, 1)[0].fitness.values
        logger.warning(color_msg([("[INFOS] ", "d_yellow"), (f"Generation [","rst"), (f"{gen}","d_cyan"), (f"]: Avg Fitness = ","rst"), (f"{avg_fitness:.2f}","d_green"), (f", Best Fitness = ","rst"), (f"{best_fitness}","d_green")]))
        current_best_fitness = tools.selBest(pop, 1)[0].fitness.values[0]
        if (best_fitness_so_far - current_best_fitness) / best_fitness_so_far > convergence_threshold:
            best_fitness_so_far = current_best_fitness
            generations_without_improvement = 0
        else:
            generations_without_improvement += 1
        if generations_without_improvement >= num_generations_threshold:
            logger.warning(color_msg([("[INFOS] ", "d_yellow"), (f"Convergence reached after {gen} generations.","rst")]))
            break
    return pareto_front

def extract_purchasing_plan(solution, card_details_df, buylist):
    purchasing_plan = []
    for idx in solution:
        if idx not in card_details_df.index:
            print(f"Invalid index: {idx}")
            continue
        card_row = card_details_df.loc[idx]
        card_name = card_row['Name']
        if card_name in buylist['Name'].values:
            buylist_row = buylist[buylist['Name'] == card_name].iloc[0]
            required_quantity = buylist_row['Quantity']
            if required_quantity > 0:
                available_quantity = min(card_row['Quantity'], required_quantity)
                purchase_details = {
                    'Name': card_name,
                    'Quantity': available_quantity,
                    'Site': card_row['Site'],
                    'Quality': card_row['Quality'],
                    'Price': card_row['Price'],
                    'Total Price': card_row['Price'] * available_quantity
                }
                purchasing_plan.append(purchase_details)
                buylist.at[buylist[buylist['Name'] == card_name].index[0], 'Quantity'] = required_quantity - available_quantity
    buylist = buylist[buylist['Quantity'] > 0]
    return purchasing_plan
