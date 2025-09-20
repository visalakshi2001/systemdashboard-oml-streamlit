import json
import uuid
import hashlib
from collections import defaultdict
import networkx as nx

# ----------- Hard-coded input/output file paths -----------
# INPUT_FILE = "../reports/Requirements.json"
# OUTPUT_FILE = "tests.json"
# ---------------------------------------------------------


def generate_tests(data):

    requirements = data["results"]["bindings"]

    # --- Build scenario sets and indexes, preserving insertion order ---
    scenario_sets_list = []  # Ordered list of scenario sets (as frozen sets)
    scenario_sets_seen = set()  # For quick membership check
    
    rqts_by_ss = defaultdict(list)  # Map: scenario_set -> [req_ids in order]
    rqts_by_ss_set = defaultdict(set)  # For quick membership check
    rqts_by_qty = defaultdict(set)  # Map: quantity -> set(req_ids)
    qty_by_rqt = {}  # Map: req_id -> quantity

    for rh in requirements:
        req_id = rh["reqName"]["value"]
        quantity = rh["quaID"]["value"]
        
        if req_id is None or quantity is None:
            continue

        # Process configs for this requirement
        scenarios = rh["scenarios"]["value"].split(",")
        ss = frozenset(scenarios)


        if ss not in scenario_sets_seen:
            scenario_sets_seen.add(ss)
            scenario_sets_list.append(ss)

        if req_id not in rqts_by_ss_set[ss]:
            rqts_by_ss_set[ss].add(req_id)
            rqts_by_ss[ss].append(req_id)

        rqts_by_qty[quantity].add(req_id)
        qty_by_rqt[req_id] = quantity

    # --- Build graph: directed edges from superset to subset ---
    g = nx.DiGraph()
    for ss in scenario_sets_list:
        g.add_node(ss)

    for v1 in scenario_sets_list:
        for v2 in scenario_sets_list:
            if v1 < v2:
                g.add_edge(v2, v1)

    # --- Generate tests in the same order as vertices were added ---
    tests = []
    for ss in scenario_sets_list:
        rqmts_direct = set(rqts_by_ss[ss])
        rqmts = set(rqmts_direct)

        for adjacent in g.successors(ss):
            rqmts.update(rqts_by_ss[adjacent])

        quantities = set()
        for r in rqmts:
            if r in qty_by_rqt:
                quantities.add(qty_by_rqt[r])
        quantities = sorted(quantities)

        qh = {}
        for q in quantities:
            reqs_for_q = rqts_by_qty[q].intersection(rqmts)
            qh[q] = {"requirements": sorted(reqs_for_q)}

        quantities_direct = []
        for q in quantities:
            if q in qh:
                if any(r in rqmts_direct for r in qh[q]["requirements"]):
                    quantities_direct.append(q)

        config = sorted(ss)
        digest_string = str(config).replace("'", '"')
        config_digest = hashlib.md5(digest_string.encode("utf-8")).hexdigest()

        rqmts_direct_list = rqts_by_ss[ss]

        test_obj = {
            "uuid": str(uuid.uuid4()),
            "config_digest": config_digest,
            "scenarios": config,
            "quantities": qh,
            "requirements_direct": rqmts_direct_list,
            "quantities_direct": quantities_direct
        }
        tests.append(test_obj)

    return tests
