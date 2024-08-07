# backend/app/utils/optimization.py
from app.models.card import MarketplaceCard, UserBuylistCard
from app.extensions import db
import pulp
import random
import pandas as pd
from deap import base, creator, tools, algorithms
from functools import partial
import logging

logger = logging.getLogger(__name__)

# DEAP Setup
creator.create("FitnessMulti", base.Fitness, weights=(-1.0, 1.0, 1.0, -1.0))
creator.create("Individual", list, fitness=creator.FitnessMulti)

class PurchaseOptimizer:
    def __init__(self, card_details_df, buylist_df, config):
        self.card_details_df = card_details_df
        self.buylist_df = buylist_df
        self.config = config

    def convert_to_dataframe(items):
        return pd.DataFrame([item.to_dict() for item in items])
    
    def run_milp_optimization(self):
        return self._run_pulp()

    def run_nsga_ii_optimization(self, milp_solution=None):
        return self._run_nsga_ii(milp_solution)

    def run_optimization(self):
        if self.config['milp_strat']:
            results, iterations = self.run_milp_optimization()
        elif self.config['nsga_algo_strat']:
            results = self.run_nsga_ii_optimization()
        elif self.config['hybrid_strat']:
            milp_solution, _ = self.run_milp_optimization()
            if milp_solution is not None:
                results = self.run_nsga_ii_optimization(milp_solution)
            else:
                results = self.run_nsga_ii_optimization()
        else:
            raise ValueError("No valid optimization strategy specified in config")

        if results is None:
            return None

        if isinstance(results, pd.DataFrame):
            sites_results = results.to_dict('records')
        else:
            sites_results = [self.get_purchasing_plan(solution) for solution in results]

        return {
            'sites_results': sites_results,
            'iterations': iterations if 'iterations' in locals() else None
        }

    def get_purchasing_plan(self, solution):
        return self._extract_purchasing_plan(solution)

    def _run_pulp(self):
        unique_cards = self.buylist_df['Name'].unique()
        unique_stores = self.card_details_df['Site'].unique()
        total_qty = self.buylist_df['Quantity'].sum()

        high_cost = 10000  # High cost for unavailable card-store combinations

        costs = {}
        for card in unique_cards:
            costs[card] = {}
            for store in unique_stores:
                price = self.card_details_df[(self.card_details_df['Name'] == card) & (self.card_details_df['Site'] == store)]['Weighted_Price'].min()
                costs[card][store] = high_cost if pd.isna(price) else price

        if self.config['find_min_store']:
            min_stores = 1
            max_stores = len(unique_stores)
            best_result = None
            all_iterations = []

            while min_stores <= max_stores:
                self.config['min_store'] = min_stores
                prob, buy_vars, store_vars = self._setup_prob(costs, unique_cards, unique_stores)

                if pulp.LpStatus[prob.status] == 'Optimal':
                    result = self._process_result(buy_vars, store_vars, costs, total_qty)
                    all_iterations.append(result)

                    if result['total_cards'] == total_qty:
                        best_result = result
                        break

                min_stores += 1

            if best_result is None:
                logger.warning("No optimal solution found for any number of stores.")
                return None, all_iterations

            return best_result['sorted_results_df'], all_iterations

        else:
            prob, buy_vars, store_vars = self._setup_prob(costs, unique_cards, unique_stores)

            if pulp.LpStatus[prob.status] != 'Optimal':
                logger.warning("Solver did not find an optimal solution.")
                return None, None

            result = self._process_result(buy_vars, store_vars, costs, total_qty)
            return result['sorted_results_df'], None


    def _run_nsga_ii(self, milp_solution=None):
        toolbox = self._initialize_toolbox()

        NGEN, MU, CXPB, MUTPB = 1000, 3000, 0.5, 0.2
        ELITISM_SIZE = int(0.1 * MU)

        if milp_solution:
            milp_individual = self._milp_solution_to_individual(milp_solution)
            pop = self._initialize_population_with_milp(MU, milp_individual)
        else:
            pop = toolbox.population(n=MU)

        fitnesses = map(toolbox.evaluate, pop)
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        pareto_front = tools.ParetoFront()
        
        convergence_threshold = 0.01
        num_generations_threshold = 10
        best_fitness_so_far = float('inf')
        generations_without_improvement = 0

        for gen in range(NGEN):
            offspring = algorithms.varAnd(pop, toolbox, CXPB, MUTPB)
            fitnesses = map(toolbox.evaluate, offspring)
            for ind, fit in zip(offspring, fitnesses):
                ind.fitness.values = fit

            pop = toolbox.select(pop + offspring, MU)
            pareto_front.update(pop)

            current_best_fitness = tools.selBest(pop, 1)[0].fitness.values[0]
            if (best_fitness_so_far - current_best_fitness) / best_fitness_so_far > convergence_threshold:
                best_fitness_so_far = current_best_fitness
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1

            if generations_without_improvement >= num_generations_threshold:
                logger.info(f"Convergence reached after {gen} generations.")
                break

        return pareto_front

    def _setup_prob(self, costs, unique_cards, unique_stores):
        prob = pulp.LpProblem("MTGCardOptimization", pulp.LpMinimize)
        buy_vars = pulp.LpVariable.dicts("Buy", (unique_cards, unique_stores), 0, 1, pulp.LpBinary)
        store_vars = pulp.LpVariable.dicts("Store", unique_stores, 0, 1, pulp.LpBinary)

        # Objective: Minimize cost
        prob += pulp.lpSum([buy_vars[card][store] * costs[card][store] for card in unique_cards for store in unique_stores])

        # Constraints
        for card in unique_cards:
            required_quantity = self.buylist_df[self.buylist_df['Name'] == card]['Quantity'].iloc[0]
            prob += pulp.lpSum([buy_vars[card][store] for store in unique_stores]) == required_quantity

        # Store usage constraint
        for store in unique_stores:
            prob += store_vars[store] >= pulp.lpSum([buy_vars[card][store] for card in unique_cards]) / len(unique_cards)

        # Minimum number of stores constraint
        prob += pulp.lpSum([store_vars[store] for store in unique_stores]) >= self.config['min_store']

        # Maximum number of stores constraint (optional)
        if 'max_store' in self.config:
            prob += pulp.lpSum([store_vars[store] for store in unique_stores]) <= self.config['max_store']

        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        return prob, buy_vars, store_vars

    def _process_result(self, buy_vars, store_vars, costs, total_qty):
        total_price = 0.0
        results = []
        total_card_nbr = 0
        stores_used = set()

        for card, store_dict in buy_vars.items():
            for store, var in store_dict.items():
                quantity = var.value()
                if quantity > 0:
                    price_per_unit = costs[card][store]
                    card_store_total_price = quantity * price_per_unit

                    if price_per_unit != 10000:  # Not a high-cost penalty
                        total_price += card_store_total_price
                        total_card_nbr += quantity
                        stores_used.add(store)

                        card_data = self.card_details_df[
                            (self.card_details_df['Name'] == card) & 
                            (self.card_details_df['Site'] == store)
                        ].iloc[0]

                        results.append({
                            "Card": card,
                            "Store": store,
                            "Quantity": quantity,
                            "Price": price_per_unit,
                            "Total Price": card_store_total_price,
                            "Quality": card_data['Quality'],
                            "Language": card_data['Language']
                        })

        results_df = pd.DataFrame(results)
        sorted_results_df = results_df.sort_values(by=['Store', 'Card'])
        sorted_results_df.reset_index(drop=True, inplace=True)

        num_stores_used = len(stores_used)
        store_usage_counts = sorted_results_df['Store'].value_counts()
        store_usage_str = ', '.join([f"{store}: {count}" for store, count in store_usage_counts.items()])

        logger.info(f"Optimization Results:")
        logger.info(f"Total price of all purchases: ${total_price:.2f}")
        logger.info(f"Total number of cards purchased: {total_card_nbr}/{total_qty}")
        logger.info(f"Number of stores used: {num_stores_used}")
        logger.info(f"Stores used: {store_usage_str}")

        return {
            "sorted_results_df": sorted_results_df,
            "total_price": total_price,
            "total_cards": total_card_nbr,
            "num_stores": num_stores_used,
            "stores_used": store_usage_str
        }


    def _initialize_toolbox(self):
        toolbox = base.Toolbox()
        toolbox.register("attr_idx", random.randint, 0, len(self.card_details_df) - 1)
        toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_idx, n=sum(self.buylist_df['Quantity']))
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate", self._evaluate_solution_wrapper())
        toolbox.register("mate", self._custom_crossover)
        toolbox.register("mutate", partial(self._custom_mutation))
        toolbox.register("select", tools.selNSGA2)
        return toolbox

    def _custom_crossover(self, ind1, ind2):
        for i in range(len(ind1)):
            if random.random() < 0.5:
                ind1[i], ind2[i] = ind2[i], ind1[i]
        return ind1, ind2

    def _custom_mutation(self, individual, indpb=0.05):
        for i in range(len(individual)):
            if random.random() < indpb:
                mutation_index = random.randrange(len(individual))
                card_name = self.buylist_df.iloc[mutation_index]['Name']
                available_options = self.card_details_df[self.card_details_df['Name'] == card_name]
                if not available_options.empty:
                    selected_option = available_options.sample(n=1)
                    individual[mutation_index] = selected_option.index.item()
        return individual,

    def _evaluate_solution_wrapper(self):
        def evaluate_solution(individual):
            total_cost = 0
            total_quality_score = 0
            stores = set()
            card_counters = {row['Name']: row['Quantity'] for _, row in self.buylist_df.iterrows()}
            card_availability = {row['Name']: 0 for _, row in self.buylist_df.iterrows()}
            language_penalty = 999
            quality_weights = {'NM': 9, 'LP': 7, 'MP': 3, 'HP': 1, 'DMG': 0}
            
            all_cards_present = all(card_counters[getattr(card_row, 'Name')] > 0 for card_row in self.card_details_df.itertuples())
            if not all_cards_present:
                return (float('inf'),)

            for idx in individual:
                if idx not in self.card_details_df.index:
                    logger.warning(f"Invalid index: {idx}")
                    continue
                card_row = self.card_details_df.loc[idx]
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

    def _extract_purchasing_plan(self, solution):
        purchasing_plan = []
        buylist = self.buylist_df.copy()
        for idx in solution:
            if idx not in self.card_details_df.index:
                logger.warning(f"Invalid index: {idx}")
                continue
            card_row = self.card_details_df.loc[idx]
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

                    # Update buylist
                    buylist.loc[buylist['Name'] == card_name, 'Quantity'] -= available_quantity

        # Remove entries with zero quantity left
        buylist = buylist[buylist['Quantity'] > 0]

        return purchasing_plan

    def _initialize_population_with_milp(self, n, milp_solution):
        population = [self._initialize_individual() for _ in range(n-1)]
        milp_individual = self._milp_solution_to_individual(milp_solution)
        population.insert(0, milp_individual)
        return population

    def _initialize_individual(self):
        individual = []
        for _, card in self.buylist_df.iterrows():
            available_options = self.card_details_df[self.card_details_df['Name'] == card['Name']]
            if not available_options.empty:
                selected_option = available_options.sample(n=1)
                individual.append(selected_option.index.item())
            else:
                logger.warning(f"Card {card['Name']} not available in any store!")
        return creator.Individual(individual)

    def _milp_solution_to_individual(self, milp_solution):
        return creator.Individual(milp_solution)