import re
from urllib.parse import urlparse
import pandas as pd
from num2words import num2words

# REMOVE THE EXCESS INFO FROM HTTPS
# ------------------------------------------------------------
# Regex library
# ------------------------------------------------------------
PATTERNS = {
    "class":        re.compile(r'^<([^>]+)>\s+<http:\S+#subClassOf>'),
    "on_property":  re.compile(r'<http:\S+#onProperty>\s+<([^>]+)>'),
    # Cardinalities (qualified and unqualified)
    "min_card":     re.compile(r'<http://www\.w3\.org/2002/07/owl#minQualifiedCardinality>\s+(\d+)'),
    "min_card_u":   re.compile(r'<http://www\.w3\.org/2002/07/owl#minCardinality>\s+(\d+)'),
    "max_card":     re.compile(r'<http://www\.w3\.org/2002/07/owl#maxQualifiedCardinality>\s+(\d+)'),
    "max_card_u":   re.compile(r'<http://www\.w3\.org/2002/07/owl#maxCardinality>\s+(\d+)'),
    "exact_card":   re.compile(r'<http://www\.w3\.org/2002/07/owl#qualifiedCardinality>\s+(\d+)'),
    "exact_card_u": re.compile(r'<http://www\.w3\.org/2002/07/owl#cardinality>\s+(\d+)'),
    # Value‑restrictions
    "some_values":  re.compile(r'<http://www\.w3\.org/2002/07/owl#someValuesFrom>\s+<([^>]+)>'),
    "all_values":   re.compile(r'<http://www\.w3\.org/2002/07/owl#allValuesFrom>\s+<([^>]+)>'),
    "has_value_iri":re.compile(r'<http://www\.w3\.org/2002/07/owl#hasValue>\s+<([^>]+)>'),
    "has_value_lit":re.compile(r'<http://www\.w3\.org/2002/07/owl#hasValue>\s+"([^"]+)"'),
    # Datatype facets inside a withRestrictions list
    "min_inc":      re.compile(r'xsd:minInclusive\s+"?([^\s"]+)'),
    "min_exc":      re.compile(r'xsd:minExclusive\s+"?([^\s"]+)'),
    "max_inc":      re.compile(r'xsd:maxInclusive\s+"?([^\s"]+)'),
    "max_exc":      re.compile(r'xsd:maxExclusive\s+"?([^\s"]+)'),
    # Violating individual (first IRI before the CDATA closes)
    "instance":     re.compile(r'^<([^>]+)>\s+<[^>]+#\w+>'),
}

def split_iri(iri: str):
    """Return (namespace‑part, local‑name)."""
    if "#" in iri:
        return iri.rsplit("#", 1)
    return iri.rsplit("/", 1)[0], iri.rsplit("/", 1)[-1]

# ------------------------------------------------------------
# Parsing a single <failure> CDATA block
# ------------------------------------------------------------
def parse_failure_block(text: str):
    """
    Parse one CDATA block and return:
      dict with basic (1)…(6) info  +  'restriction' descriptor for NL sentence.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("//")]

    data = {
        "Class": None, "Object property": None, "Object property range": None,
        "Ontology": None, "Instance": None, "Description": None,
        # extra restriction info
        "rtype": None, "n": None, "range_text": None,
        "literal": None, "facet_min": None, "facet_max": None
    }

    # Pass 1 – structural pieces (class, property, cardinalities, etc.)
    for ln in lines:
        if not data["Class"]:
            m = PATTERNS["class"].match(ln)
            if m: data["Class"] = m.group(1); continue
        if not data["Object property"]:
            m = PATTERNS["on_property"].search(ln)
            if m: data["Object property"] = m.group(1); continue

        # Cardinalities
        # if PATTERNS["min_card"].search(ln):
        #     st.write(PATTERNS["min_card"].search(ln).group(1))
        if m := PATTERNS["min_card"].search(ln) or PATTERNS["min_card_u"].search(ln):
            data["rtype"], data["n"] = "min", int(m.group(1))
        if m := PATTERNS["max_card"].search(ln) or PATTERNS["max_card_u"].search(ln):
            data["rtype"], data["n"] = "max", int(m.group(1))
        if m := PATTERNS["exact_card"].search(ln) or PATTERNS["exact_card_u"].search(ln):
            data["rtype"], data["n"] = "exact", int(m.group(1))

        # Existential / universal & hasValue
        if not data["rtype"]:
            if m := PATTERNS["some_values"].search(ln):
                data["rtype"], data["range_text"] = "some", m.group(1)
            elif m := PATTERNS["all_values"].search(ln):
                data["rtype"], data["range_text"] = "all", m.group(1)
            elif m := PATTERNS["has_value_iri"].search(ln):
                data["rtype"], data["literal"] = "hasValue", m.group(1)
            elif m := PATTERNS["has_value_lit"].search(ln):
                data["rtype"], data["literal"] = "hasValue", m.group(1)

        # Datatype facets (they often appear together; we capture them all)
        if m := PATTERNS["min_inc"].search(ln):
            data["facet_min"] = (m.group(1), "inclusive")
            data["rtype"] = "datatype"
        if m := PATTERNS["min_exc"].search(ln):
            data["facet_min"] = (m.group(1), "exclusive")
            data["rtype"] = "datatype"
        if m := PATTERNS["max_inc"].search(ln):
            data["facet_max"] = (m.group(1), "inclusive")
            data["rtype"] = "datatype"
        if m := PATTERNS["max_exc"].search(ln):
            data["facet_max"] = (m.group(1), "exclusive")
            data["rtype"] = "datatype"

        # Range class for cardinality / universal etc.
        if not data["Object property range"]:
            card_range_pat = re.compile(r'<http://www\.w3\.org/2002/07/owl#on(Class|Data)>\s+<([^>]+)>')
            if m := card_range_pat.search(ln):
                data["Object property range"] = m.group(2)

    # Pass 2 – instance line (scan backwards – usually last line)
    for ln in reversed(lines):
        if m := PATTERNS["instance"].match(ln):
            data["Instance"] = m.group(1)
            break

    # Essential triples found?
    if not (data["Class"] and data["Object property"] and data["Instance"]):
        return None

    data["Ontology"] = split_iri(data["Class"])[0]
    data["Description"] = data["Instance"].rsplit('/', 1)[-1].strip()

    # If range not yet set and we parsed range_text earlier:
    if not data["Object property range"]:
        data["Object property range"] = data.get("range_text")

    return data

# ------------------------------------------------------------
# 2‑column DataFrame
# ------------------------------------------------------------
def failure_to_dataframe(d):
    d["Class"] = d["Class"].rsplit('/', 1)[-1].strip().split("#")[-1]
    d["Object property"] = d["Object property"].rsplit('/', 1)[-1].strip().split("#")[-1]
    d["Object property range"] = d["Object property range"].rsplit('/', 1)[-1].strip().split("#")[-1]
    d["Instance"] = d["Instance"].rsplit('/', 1)[-1].strip().split("#")[-1]
    d["Description"] = d["Description"].split("#")[0]
    d["Ontology"] = d["Ontology"].rsplit('/', 1)[-1].strip().split("#")[-1]
    rows = [
        {"Item": "(1) Class",               "Value": d["Class"]},
        {"Item": "(2) Object property",     "Value": d["Object property"]},
        {"Item": "(3) Object property range", "Value": d["Object property range"]},
        {"Item": "(4) Ontology",            "Value": d["Ontology"]},
        {"Item": "(5) Instance",            "Value": d["Instance"]},
        {"Item": "(6) Description",         "Value": d["Description"]},
    ]
    return pd.DataFrame(rows)

# ------------------------------------------------------------
# Natural‑language explanation
# ------------------------------------------------------------
def natural_language_message(d):
    cls  = split_iri(d["Class"])[1]
    prop = split_iri(d["Object property"])[1]
    inst = split_iri(d["Instance"])[1]

    if d["rtype"] == "min":
        rng = split_iri(d["Object property range"])[1]
        return (f"A **{cls}** must have <ins>at least {num2words(d['n'])}</ins> **{prop}** relation "
                f"to **{rng}**. Individual **{inst}** violates this.")
    if d["rtype"] == "max":
        rng = split_iri(d["Object property range"])[1]
        return (f"A **{cls}** must have **at most {d['n']}** link(s) via **{prop}** "
                f"to **{rng}**. Individual **{inst}** violates this.")
    if d["rtype"] == "exact":
        rng = split_iri(d["Object property range"])[1]
        return (f"A **{cls}** must have **exactly {d['n']}** link(s) via **{prop}** "
                f"to **{rng}**. Individual **{inst}** violates this.")
    if d["rtype"] == "some":
        rng = split_iri(d["Object property range"])[1]
        return (f"A **{cls}** must have **at least one** **{prop}** link to a **{rng}** "
                f"but **{inst}** has none.")
    if d["rtype"] == "all":
        rng = split_iri(d["Object property range"])[1]
        return (f"**All** **{prop}** values of a **{cls}** must be **{rng}**. "
                f"Individual **{inst}** does not satisfy this.")
    if d["rtype"] == "hasValue":
        val = d["literal"] or split_iri(d["literal"])[1]
        return (f"A **{cls}** must have value **{val}** via **{prop}**, "
                f"but **{inst}** does not.")
    if d["rtype"] == "datatype":
        parts = []
        if d["facet_min"]:
            v, incl = d["facet_min"]
            parts.append(f"≥ {v}" if incl == "inclusive" else f"> {v}")
        if d["facet_max"]:
            v, incl = d["facet_max"]
            parts.append(f"≤ {v}" if incl == "inclusive" else f"< {v}")
        rng_text = " and ".join(parts)
        return (f"Values of **{prop}** for a **{cls}** must be {rng_text}. \n"
                f"Individual **{inst}** violates this.")
    # Fallback
    return f"Individual **{inst}** violates an unspecified restriction on **{prop}**."

