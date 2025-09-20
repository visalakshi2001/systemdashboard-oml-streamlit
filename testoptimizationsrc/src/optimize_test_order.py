"""
Python translation of optimize-test-order.rb
Optimizes test execution order using TSP algorithms to minimize reconfiguration costs.
Improved version with closer match to Ruby's 2-opt implementation.
"""

import json
import sys
import argparse
import random
import logging
from typing import List, Dict, Any, Tuple

# ----------- Hard-coded input/output file paths -----------
# COST_MAP_FILE = "costs.json"
# TESTS_INPUT_FILE = "pruned_tests.json"
# OUTPUT_FILE = "test_order_optimized.json"
# ---------------------------------------------------------


class TSP2Opt:
    """2-opt TSP solver - closer match to Ruby implementation"""
    
    def __init__(self, weights: List[List[float]]):
        self.dimension = len(weights)
        self.weights = weights
        self.tour = list(range(self.dimension))
        # Calculate initial cost exactly like Ruby
        self.cost = self._calculate_initial_cost()
    
    def _calculate_initial_cost(self) -> float:
        """Calculate initial tour cost matching Ruby's approach"""
        total_cost = 0
        for i in range(self.dimension):
            j = (i + 1) % self.dimension
            total_cost += self.distance(self.tour[i], self.tour[j])
        return total_cost
    
    def distance(self, i: int, j: int) -> float:
        """Get distance between cities i and j - matching Ruby's method"""
        if j < i:
            return self.weights[i][j]
        else:
            return self.weights[j][i]
    
    def swap_edges(self, i: int, j: int):
        """Swap edges - matching Ruby's implementation exactly"""
        i += 1  # Ruby increments i first
        while i < j:
            self.tour[i], self.tour[j] = self.tour[j], self.tour[i]
            i += 1
            j -= 1
    
    def optimize(self):
        """Run 2-opt optimization - matching Ruby's algorithm exactly"""
        found_improvement = True
        
        while found_improvement:
            found_improvement = False
            
            # Match Ruby's loop structure exactly: for i in 0..(@dimension - 2)
            for i in range(self.dimension - 1):  # 0 to dimension-2
                # Match Ruby's: for j in (i + 2)..(@dimension - 1)
                for j in range(i + 2, self.dimension):  # i+2 to dimension-1
                    # Calculate cost delta exactly as Ruby does
                    cost_delta = (
                        0
                        - self.distance(self.tour[i], self.tour[i + 1])
                        - self.distance(self.tour[j], self.tour[(j + 1) % self.dimension])
                        + self.distance(self.tour[i], self.tour[j])
                        + self.distance(self.tour[i + 1], self.tour[(j + 1) % self.dimension])
                    )
                    
                    if cost_delta < 0:
                        # Perform swap exactly like Ruby
                        self.swap_edges(i, j)
                        self.cost += cost_delta
                        found_improvement = True
                        # Important: Ruby doesn't break here, it continues checking


class OptimizeTestOrder:
    """Main test order optimization class"""
    
    def __init__(self):
        self.logger = logging.getLogger('optimize-test-order')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('I, [%(asctime)s] INFO -- optimize-test-order: %(message)s', 
                                        datefmt='%Y-%m-%dT%H:%M:%S')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def make_weights(self, tests: List[Dict], cost_map: Dict[str, int]) -> List[List[float]]:
        """Create weight matrix for TSP"""
        n = len(tests)
        weights = []
        
        for i in range(n):
            row = []
            si = set(tests[i]['scenarios'])
            for j in range(i + 1):
                sj = set(tests[j]['scenarios'])
                apply = sj - si
                retract = si - sj
                cost = sum(cost_map.get(str(e), 0) for e in (apply | retract))
                row.append(cost)
            weights.append(row)
        
        return weights
    
    def run(self, args: argparse.Namespace, input_data: str) -> Dict:
        """Main optimization routine"""
        
        # Load cost map
        self.logger.info("loading cost map")
        with open(args.cost_map, 'r') as f:
            cost_map_data = json.load(f)
        
        scenarios_cost = cost_map_data['scenarios']
        observations_cost = cost_map_data['observations']
        
        self.logger.info(f"loaded {len(scenarios_cost) + len(observations_cost)} cost map entries")
        
        # Parse input tests
        tests_data = json.loads(input_data)
        
        # Prepare tests list with initial empty configuration
        if args.resort:
            tests = sorted(tests_data, key=lambda x: random.random())
        else:
            tests = tests_data.copy()
        
        # Add initial empty test configuration at the beginning
        tests.insert(0, {'id': 0, 'scenarios': [], 'quantities': {}})
        
        # Create weight matrix
        weights = self.make_weights(tests, scenarios_cost)
        
        # Calculate observation cost
        observation_cost = sum(
            sum(observations_cost.get(q, 0) for q in t.get('quantities', {}).keys())
            for t in tests
        )
        
        # Optimize tour
        if args.concorde:
            # Concorde solver would go here - not implemented in this translation
            self.logger.warning("Concorde solver not available in Python, using 2-opt instead")
        
        tsp = TSP2Opt(weights)
        self.logger.info(f"initial tour cost: {tsp.cost}")
        
        if args.optimize:
            tsp.optimize()
        
        tour = tsp.tour
        reconfiguration_cost = tsp.cost
        
        self.logger.info(f"optimized tour cost: {reconfiguration_cost}")
        
        # Rotate tour to start with the empty configuration (id=0)
        init_idx = None
        for idx, tour_idx in enumerate(tour):
            if tests[tour_idx]['id'] == 0:
                init_idx = idx
                break
        
        if init_idx is None:
            raise ValueError("Initial empty configuration not found in tour")
        
        if init_idx == 0:
            order = tour
        else:
            order = tour[init_idx:] + tour[:init_idx]
        
        # Build ordered tests
        tests_tour = [tests[i] for i in order]
        
        # Generate optimized test list with retract/apply operations
        opt_tests = []
        test_count = 0
        
        while len(tests_tour) >= 2:
            pair = tests_tour[:2]
            
            current_scenarios = set(pair[0]['scenarios'])
            next_scenarios = set(pair[1]['scenarios'])
            
            retract = sorted(list(current_scenarios - next_scenarios))
            apply = sorted(list(next_scenarios - current_scenarios))
            
            test_count += 1
            opt_test = pair[1].copy()
            opt_test.update({
                'id': test_count,
                'scenarios': sorted(list(next_scenarios)),
                'retract': retract,
                'apply': apply
            })
            opt_tests.append(opt_test)
            
            tests_tour.pop(0)
        
        self.logger.info(f"emitting {len(opt_tests)} test configurations")
        
        return {
            'reconfiguration_cost': reconfiguration_cost,
            'observation_cost': observation_cost,
            'tests': opt_tests
        }


def optimize_test_order(pruned_tests_json, costs_json):
    """Main entry point (hard-coded I/O version)"""
    try:
        # Read input tests JSON
        with open(pruned_tests_json, 'r') as f:
            input_data = f.read()

        # Build a minimal args namespace expected by OptimizeTestOrder.run()
        class Args: pass
        args = Args()
        args.cost_map = costs_json
        args.resort = False
        args.concorde = False
        args.no_optimize = False
        args.optimize = True  # inverse of no_optimize

        # Run optimization
        optimizer = OptimizeTestOrder()
        result = optimizer.run(args, input_data)

        # # Write output JSON
        # with open(OUTPUT_FILE, 'w') as f:
        #     json.dump(result, f, indent=2)

        # print(f"Optimized test order written to {OUTPUT_FILE}")
        return result

    except FileNotFoundError as e:
        print(f"Error: File not found: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: JSON decode error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# if __name__ == '__main__':
#     sys.exit(main())
