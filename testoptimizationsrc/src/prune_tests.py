import sys
import json
import logging

# ----------- Hard-coded input/output file paths -----------
# SUFFICIENCY_FILE = "../reports/sufficient.json"
# TESTS_INPUT_FILE = "tests.json"
# OUTPUT_FILE = "pruned_tests.json"
# ---------------------------------------------------------


# def setup_logging():
#     """Set up simple logging"""
#     logging.basicConfig(
#         level=logging.INFO,
#         format='INFO: %(message)s',
#         stream=sys.stderr
#     )
#     return logging.getLogger('prune-tests')


def prune_tests(tests_data, sufficiency_data):
    """
    Prune tests based on sufficiency data - exact Ruby logic translation
    """
    logger = logging.getLogger('prune-tests')
    
    # Build sufficients mapping exactly like Ruby
    sufficients = {}
    for sh in sufficiency_data["results"]["bindings"]:
        req_id = sh["reqName"]["value"]
        config_sets = {frozenset(sh["scenarios"]["value"].split(","))}
        sufficients[req_id] = config_sets
    
    # Process each test exactly like Ruby
    drop_tests = []
    
    for test in tests_data:
        t_uuid = test['uuid']
        config = frozenset(test['scenarios'])
        
        drop_quantities = []
        for q_id in list(test['quantities'].keys()):
            qh = test['quantities'][q_id]

            keep_requirements = []
            for r_id in qh['requirements']:
                if r_id in sufficients:
                    if config in sufficients[r_id]:
                        keep_requirements.append(r_id)
                    else:
                        logger.info(f"drop requirement {r_id} from test {t_uuid}")
                else:
                    keep_requirements.append(r_id)

            qh['requirements'] = keep_requirements
            if not qh['requirements']:
                drop_quantities.append(q_id)

        for drop_q in drop_quantities:
            logger.info(f"drop quantity {drop_q} from test {t_uuid}")
            del test['quantities'][drop_q]

        if not test['quantities']:
            drop_tests.append(test)

    for drop_t in drop_tests:
        logger.info(f"drop test {drop_t['uuid']}")
        tests_data.remove(drop_t)

    return tests_data


# def main():
#     """Main function matching Ruby's run method"""
#     logger = setup_logging()
    
#     try:
#         # Read sufficiency data from hard-coded file
#         with open(SUFFICIENCY_FILE, 'r') as f:
#             sufficients_json = json.load(f)
        
#         # Read tests data from hard-coded file
#         with open(TESTS_INPUT_FILE, 'r') as f:
#             tests = json.load(f)
        
#         # Prune the tests
#         pruned_tests = prune_tests(tests, sufficients_json)
        
#         # Write output to hard-coded file
#         with open(OUTPUT_FILE, 'w') as f:
#             json.dump(pruned_tests, f, indent=2)

#         print(f"Pruned tests written to {OUTPUT_FILE}")
#         return 0
        
#     except FileNotFoundError as e:
#         print(f"Error: File not found: {e}", file=sys.stderr)
#         return 1
#     except json.JSONDecodeError as e:
#         print(f"Error: JSON decode error: {e}", file=sys.stderr)
#         return 1
#     except Exception as e:
#         print(f"Error: {e}", file=sys.stderr)
#         return 1


# if __name__ == "__main__":
#     sys.exit(main())
