"""
graph/nodes/query_analyzer.py
------------------------------
Node 1 of 4 in the LangGraph pipeline.

Responsibility:
  Take the raw user query and extract:
    - product_description  : clean product description
    - hts_search_term      : rephrased in HTS legal vocabulary for retrieval
    - origin_country       : where the product is made/shipped from
    - trade_scenario       : what the user actually wants to know
    - analyzer_notes       : brief reasoning (for debug/transparency)

  Example:
    Input:  "gaming laptop from China, what's the duty?"
    Output:
      product_description : "gaming laptop computer"
      hts_search_term     : "portable automatic data processing machine"
      origin_country      : "China"
      trade_scenario      : "import_duty"

Why this matters:
  "gaming laptop" scores 0.495 against HTS heading 8471.
  "portable automatic data processing machine" scores 0.702.
  The analyzer bridges consumer language to HTS legal terminology.

Uses Ollama with llama3.1:8b (free, local).
Falls back to rule-based extraction if Ollama is unavailable.
"""

import json
import re

from graph.state import TradeQueryState

# ── LLM clients — OpenAI primary, Ollama fallback ────────────────────────────
import os

# OpenAI (used on cloud / when OPENAI_API_KEY is set)
try:
    from openai import OpenAI as _OpenAI
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False

# Ollama (used locally when OpenAI key not set)
try:
    import ollama as _ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

OPENAI_MODEL = "gpt-4o-mini"   # cheap, fast, good at JSON extraction
OLLAMA_MODEL = "llama3.1:8b"

# ── HTS vocabulary map (rule-based fallback) ──────────────────────────────────
# consumer term → HTS legal term  (longest match wins — order matters)
# Covers top 12 SME import chapters: 33,39,44,61-64,73,84,85,90,94,95
HTS_VOCAB: dict[str, str] = {

    # ── Ch 84 — Machinery / computers ────────────────────────────────────────
    "gaming laptop":        "portable automatic data processing machine weighing not more than 10 kg",
    "laptop computer":      "portable automatic data processing machine weighing not more than 10 kg",
    "laptop":               "portable automatic data processing machine weighing not more than 10 kg",
    "notebook computer":    "portable automatic data processing machine weighing not more than 10 kg",
    "desktop computer":     "automatic data processing machine",
    "desktop pc":           "automatic data processing machine",
    "computer":             "automatic data processing machine",
    "server":               "automatic data processing machine",
    "keyboard":             "keyboard input unit automatic data processing",
    "computer mouse":       "input unit automatic data processing machine",
    "usb hub":              "automatic data processing machine unit",
    "hard drive":           "magnetic disk drive storage unit",
    "external hard drive":  "magnetic disk drive storage unit",
    "ssd":                  "solid state non-volatile storage unit",
    "nvme":                 "solid state non-volatile storage unit",
    "monitor":              "display unit automatic data processing machine",
    "printer":              "printing machinery",
    "3d printer":           "printing machinery",
    "air conditioner":      "air conditioning machine",
    "air compressor":       "compressor for air",
    "hydraulic pump":       "pump for liquids hydraulic",
    "centrifugal pump":     "centrifugal pump for liquids",
    "water pump":           "pump for liquids",
    "pump":                 "pump for liquids",
    "heat exchanger":       "heat exchanger",
    "refrigerator":         "refrigerating equipment",
    "freezer":              "refrigerating equipment",
    "washing machine":      "household washing machine",
    "dishwasher":           "dishwashing machine",
    "fan":                  "ventilating fan",
    "generator":            "electric generating set",
    "engine":               "internal combustion piston engine",
    "turbine":              "hydraulic turbine",
    "conveyor":             "conveyor belt machinery",
    "forklift":             "fork-lift truck",
    "crane":                "crane lifting machinery",

    # ── Ch 85 — Electronics / electrical ─────────────────────────────────────
    "smartphone":           "telephone for cellular networks voice data",
    "mobile phone":         "telephone for cellular networks",
    "cell phone":           "telephone for cellular networks",
    "iphone":               "telephone for cellular networks",
    "android phone":        "telephone for cellular networks",
    "tablet":               "portable automatic data processing machine",
    "ipad":                 "portable automatic data processing machine",
    "smartwatch":           "wrist-worn communication device",
    "headphones":           "headphones whether or not combined with microphone",
    "earbuds":              "headphones combined with microphone",
    "earphones":            "headphones whether or not combined with microphone",
    "wireless earbuds":     "headphones combined with microphone",
    "bluetooth speaker":    "loudspeaker",
    "speaker":              "loudspeaker",
    "microphone":           "microphone",
    "led desk lamp":        "electric desk lamp light-emitting diode portable",
    "desk lamp":            "electric desk lamp portable luminaire",
    "led floor lamp":       "electric floor lamp light-emitting diode luminaire",
    "floor lamp":           "electric floor lamp luminaire",
    "table lamp":           "electric table lamp luminaire",
    "led lamp":             "light-emitting diode lamp electric",
    "led bulb":             "light-emitting diode lamp electric",
    "led strip":            "light-emitting diode strip lighting",
    "led light":            "light-emitting diode lighting electric",
    "smart bulb":           "light-emitting diode lamp electric",
    "ceiling light":        "ceiling lighting fixture luminaire",
    "chandelier":           "chandelier lighting fixture luminaire",
    "lamp":                 "electric lamp luminaire portable",
    "solar panel":          "photovoltaic cells modules panels",
    "solar module":         "photovoltaic cells modules panels",
    "battery":              "electric accumulator battery",
    "lithium battery":      "lithium-ion electric accumulator",
    "power bank":           "portable electric accumulator",
    "charger":              "electric charger apparatus",
    "cable":                "insulated electric conductor",
    "usb cable":            "insulated electric conductor",
    "electric motor":       "AC electric motor single phase excluding generating sets 8501",
    "dc motor":             "DC electric motor excluding generating sets 8501",
    "servo motor":          "AC electric motor servo control 8501",
    "induction motor":      "AC induction electric motor 8501",
    "transformer":          "electrical transformer",
    "inverter":             "static converter inverter",
    "rectifier":            "rectifier static converter",
    "pcb":                  "printed circuit board",
    "circuit board":        "printed circuit board",
    "microcontroller":      "integrated circuit microprocessor",
    "integrated circuit":   "monolithic integrated circuit",
    "chip":                 "semiconductor integrated circuit",
    "sensor":               "transducer sensor",
    "cctv camera":          "surveillance camera",
    "security camera":      "video surveillance camera",
    "webcam":               "video camera",
    "drone":                "unmanned aerial vehicle",
    "router":               "network router switching apparatus",
    "switch":               "network switching apparatus",
    "refrigerator compressor": "hermetic compressor for refrigerating",
    "air conditioning unit": "air conditioning machine",

    # ── Ch 61-62 — Apparel ────────────────────────────────────────────────────
    "t-shirt":              "knitted cotton shirt",
    "t shirt":              "knitted cotton shirt",
    "tshirt":               "knitted cotton shirt",
    "polo shirt":           "knitted cotton shirt polo",
    "hoodie":               "knitted pullover hooded",
    "hooded sweatshirt":    "knitted pullover hooded",
    "sweatshirt":           "knitted pullover sweatshirt",
    "sweater":              "knitted pullover sweater",
    "cardigan":             "knitted cardigan",
    "knit top":             "knitted women top",
    "leggings":             "knitted tights hosiery",
    "yoga pants":           "knitted women trousers",
    "activewear":           "knitted athletic garment",
    "sports bra":           "knitted women bra",
    "underwear":            "knitted men underwear",
    "boxers":               "knitted men underpants",
    "bra":                  "knitted women brassiere",
    "socks":                "knitted hosiery",
    "dress socks":          "knitted hosiery",
    "shirt":                "woven men shirt",
    "dress shirt":          "woven men shirt",
    "women blouse":         "woven women blouse",
    "blouse":               "woven women blouse shirt",
    "jeans":                "woven denim trousers men",
    "denim":                "woven denim trousers",
    "trousers":             "woven men trousers",
    "pants":                "woven men trousers",
    "chinos":               "woven men trousers cotton",
    "shorts":               "woven men shorts",
    "women dress":          "woven women dress",
    "dress":                "woven women dress",
    "skirt":                "woven women skirt",
    "jacket":               "woven men jacket outer",
    "blazer":               "woven men jacket",
    "suit":                 "woven men suit",
    "coat":                 "woven men overcoat",
    "parka":                "woven men anorak parka",
    "vest":                 "woven men waistcoat",
    "raincoat":             "woven man-made fiber raincoat",
    "swimwear":             "woven swimwear",
    "swimsuit":             "woven women swimsuit",
    "pajamas":              "woven men pajamas",
    "bathrobe":             "knitted bathrobe",
    "uniform":              "woven occupational garment",

    # ── Ch 63 — Home textiles ─────────────────────────────────────────────────
    "bedsheet":             "cotton bed linen",
    "bed sheet":            "cotton bed linen",
    "bedding set":          "cotton bed linen set",
    "pillow case":          "cotton pillow cover",
    "duvet cover":          "cotton bed linen duvet",
    "blanket":              "woven blanket",
    "towel":                "cotton terry towel",
    "bath towel":           "cotton terry bath towel",
    "curtain":              "woven curtain",
    "rug":                  "woven pile carpet",
    "carpet":               "woven tufted carpet",
    "mat":                  "textile floor mat",
    "tote bag":             "cotton tote bag",
    "canvas bag":           "cotton woven bag",
    "backpack":             "woven backpack man-made fiber",
    "handbag":              "leather handbag",
    "purse":                "leather handbag",

    # ── Ch 64 — Footwear ──────────────────────────────────────────────────────
    "sneakers":             "athletic footwear outer sole rubber plastics",
    "running shoes":        "athletic footwear outer sole rubber plastics",
    "sports shoes":         "athletic footwear outer sole rubber",
    "athletic shoes":       "athletic footwear outer sole rubber plastics",
    "sandals":              "sandals outer sole rubber plastics",
    "flip flops":           "sandals outer sole rubber",
    "boots":                "boots outer sole rubber leather",
    "ankle boots":          "ankle boots outer sole leather",
    "high heels":           "women footwear outer sole leather",
    "dress shoes":          "men footwear outer sole leather",
    "leather shoes":        "footwear outer sole rubber leather upper",
    "slippers":             "slippers outer sole rubber",
    "shoes":                "footwear outer sole rubber plastics",

    # ── Ch 39 — Plastics ──────────────────────────────────────────────────────
    "plastic bag":          "polyethylene bag",
    "poly bag":             "polyethylene bag",
    "polybag":              "polyethylene bag",
    "plastic bottle":       "polyethylene terephthalate bottle",
    "plastic container":    "plastics container",
    "food container":       "plastics food container",
    "storage container":    "plastics articles",
    "plastic box":          "plastics box articles",
    "plastic film":         "polyethylene film",
    "bubble wrap":          "plastics cellular sheet",
    "packing material":     "plastics packing material",
    "plastic tube":         "plastics tube",
    "plastic pipe":         "plastics pipe",
    "plastic tray":         "plastics tray articles",
    "plastic cup":          "plastics cup",
    "straw":                "plastics drinking straw",
    "plastic straw":        "plastics drinking straw",
    "silicone case":        "silicone rubber protective case articles",
    "phone case":           "plastics protective case articles",
    "tablet case":          "plastics protective case articles",
    "laptop case":          "plastics protective case articles",
    "phone cover":          "plastics protective cover articles",
    "silicone product":     "articles of vulcanized rubber silicone",

    # ── Ch 44 — Wood products ─────────────────────────────────────────────────
    "wooden furniture":     "wooden furniture seats",
    "wood flooring":        "wooden floor covering",
    "hardwood floor":       "wooden floor covering hardwood",
    "bamboo flooring":      "bamboo floor covering",
    "plywood":              "plywood veneered panel",
    "mdf":                  "fiberboard medium density",
    "lumber":               "sawn wood timber",
    "wooden door":          "wooden door frame",
    "wooden frame":         "wooden frame",
    "cutting board":        "wooden kitchen utensil",
    "wooden toy":           "wooden toy",

    # ── Ch 73 — Steel articles ────────────────────────────────────────────────
    "steel pipe":           "steel pipe tube",
    "steel tube":           "steel seamless tube",
    "pipe fitting":         "steel pipe fitting",
    "steel fitting":        "steel pipe fitting",
    "steel fastener":       "steel bolt nut screw",
    "bolt":                 "steel bolt",
    "screw":                "steel screw fastener",
    "nut":                  "steel nut fastener",
    "steel wire":           "steel wire rod",
    "steel chain":          "steel chain",
    "steel tool":           "steel hand tool",
    "wrench":               "steel wrench spanner",
    "steel bracket":        "steel bracket article",

    # ── Ch 94 — Furniture / lighting ─────────────────────────────────────────
    "sofa":                 "upholstered seat sofa",
    "couch":                "upholstered seat sofa",
    "chair":                "seat chair",
    "office chair":         "seat swivel office",
    "desk":                 "wooden desk furniture",
    "table":                "wooden table furniture",
    "dining table":         "wooden dining table",
    "bookshelf":            "wooden shelf furniture",
    "cabinet":              "wooden cabinet furniture",
    "dresser":              "wooden dresser furniture",
    "wardrobe":             "wooden wardrobe furniture",
    "bed frame":            "wooden bed furniture",
    "mattress":             "mattress spring",
    "pillow":               "pillow stuffed",
    "cushion":              "cushion stuffed textile",

    # ── Ch 95 — Toys / sports / games ────────────────────────────────────────
    "toy":                  "toy plastic children",
    "doll":                 "doll toy",
    "action figure":        "action figure toy",
    "board game":           "board game",
    "puzzle":               "jigsaw puzzle",
    "lego":                 "construction toy building blocks",
    "building blocks":      "construction toy building blocks",
    "video game":           "video game console",
    "gaming console":       "video game console machine",
    "rc car":               "radio-controlled toy car",
    "toy car":              "toy car wheeled",
    "bicycle":              "bicycle two-wheel",
    "scooter":              "scooter kick",
    "electric scooter":     "electric scooter",
    "skateboard":           "skateboard",
    "exercise equipment":   "exercise gymnasium equipment",
    "treadmill":            "treadmill exercise machine",
    "yoga mat":             "exercise mat rubber",
    "dumbbells":            "dumbbell weight training",
    "fishing rod":          "fishing rod tackle",
    "tent":                 "tent camping",
    "sleeping bag":         "sleeping bag",

    # ── Ch 33 — Cosmetics / personal care ────────────────────────────────────
    "perfume":              "perfume toilet water",
    "cologne":              "perfume toilet water cologne",
    "skincare":             "beauty preparation skin care",
    "face cream":           "beauty preparation face cream",
    "moisturizer":          "beauty preparation moisturizing",
    "serum":                "beauty preparation skin serum",
    "sunscreen":            "sunscreen preparation",
    "makeup":               "cosmetic beauty preparation",
    "lipstick":             "lipstick beauty preparation",
    "foundation":           "cosmetic preparation foundation",
    "mascara":              "cosmetic preparation eye",
    "shampoo":              "shampoo hair preparation",
    "conditioner":          "hair conditioner preparation",
    "hair product":         "hair preparation cosmetic",
    "body lotion":          "body lotion beauty preparation",
    "soap":                 "soap organic surface-active",
    "hand sanitizer":       "disinfectant preparation",
    "deodorant":            "deodorant preparation",
    "toothpaste":           "toothpaste dental preparation",

    # ── Ch 90 — Optical / instruments ────────────────────────────────────────
    "eyeglasses":           "spectacles corrective lenses",
    "sunglasses":           "sunglasses spectacles",
    "glasses":              "spectacles corrective",
    "contact lenses":       "contact lenses ophthalmic",
    "camera":               "digital camera photographic",
    "binoculars":           "binoculars optical",
    "microscope":           "microscope optical",
    "telescope":            "telescope optical",
    "medical device":       "medical diagnostic instrument",
    "thermometer":          "thermometer medical",
    "blood pressure monitor": "sphygmomanometer blood pressure",
    "glucose meter":        "glucometer blood analysis instrument",
    "cpap":                 "breathing apparatus medical",
    "watch":                "wristwatch",
    "clock":                "clock",
}

# ── trade scenario keywords ───────────────────────────────────────────────────
# ── chapter hint map — product keyword → likely HTS chapter ──────────────────
# Used to pre-filter vector search, avoiding cross-chapter confusion
# e.g. "electric motor" must search ch85 not ch87 (motorcycles)
CHAPTER_HINTS: dict[str, str] = {
    # ch 84 — machinery
    "laptop": "84", "computer": "84", "pump": "84", "compressor": "84",
    "engine": "84", "turbine": "84", "conveyor": "84", "forklift": "84",
    "refrigerator": "84", "washing machine": "84", "dishwasher": "84",
    "heat exchanger": "84", "printer": "84",
    # ch 85 — electronics / electrical
    "electric motor": "85", "motor": "85", "transformer": "85",
    "smartphone": "85", "phone": "85", "led": "85", "lamp": "85",
    "battery": "85", "charger": "85", "solar panel": "85",
    "headphones": "85", "earbuds": "85", "speaker": "85",
    "circuit board": "85", "pcb": "85", "inverter": "85",
    "router": "85", "switch": "85", "camera": "85",
    # ch 61 — knitted apparel
    "t-shirt": "61", "tshirt": "61", "hoodie": "61", "sweater": "61",
    "knitwear": "61", "leggings": "61", "socks": "61", "underwear": "61",
    # ch 62 — woven apparel
    "shirt": "62", "trousers": "62", "jeans": "62", "jacket": "62",
    "suit": "62", "dress": "62", "blouse": "62", "coat": "62",
    # ch 39 — plastics
    "plastic": "39", "polyethylene": "39", "polypropylene": "39",
    "silicone": "39", "pvc": "39",
    # ch 94 — furniture / lighting
    "sofa": "94", "chair": "94", "desk": "94", "table": "94",
    "mattress": "94", "wardrobe": "94", "cabinet": "94",
    # ch 64 — footwear
    "shoes": "64", "sneakers": "64", "boots": "64", "sandals": "64",
    # ch 73 — steel
    "steel pipe": "73", "pipe fitting": "73", "bolt": "73", "screw": "73",
    # ch 44 — wood
    "plywood": "44", "lumber": "44", "flooring": "44",
}


def get_chapter_hint(query: str) -> str:
    """Return a 2-digit chapter hint based on product keywords."""
    q = query.lower()
    # check multi-word keys first (longer match wins)
    for term, chapter in sorted(CHAPTER_HINTS.items(), key=lambda x: -len(x[0])):
        if term in q:
            return chapter
    return ""


SCENARIO_KEYWORDS = {
    "import_duty":   ["duty", "tariff", "rate", "import", "tax", "cost", "how much"],
    "fta_check":     ["fta", "free trade", "usmca", "nafta", "gsp", "preference",
                      "mexico", "canada", "qualify"],
    "origin_check":  ["country of origin", "made in", "origin", "where is it from",
                      "manufactured in"],
}

# ── country extraction ────────────────────────────────────────────────────────
COUNTRIES = [
    "china", "chinese", "mexico", "mexican", "canada", "canadian",
    "vietnam", "vietnamese", "india", "indian", "bangladesh",
    "indonesia", "indonesian", "thai", "thailand", "south korea", "korean",
    "japan", "japanese", "germany", "german", "taiwan", "taiwanese",
    "cambodia", "pakistan", "sri lanka", "turkey", "turkish",
    "italy", "italian", "france", "french", "portugal", "portuguese",
    "brazil", "brazilian", "malaysia", "malaysian", "philippines",
    "ethiopia", "kenya", "ghana", "morocco", "moroccan",
    "uk", "united kingdom", "britain", "british",
    "hong kong", "singapore",
]

COUNTRY_NORMALIZE = {
    "chinese": "China", "mexican": "Mexico", "canadian": "Canada",
    "vietnamese": "Vietnam", "indian": "India", "korean": "South Korea",
    "japanese": "Japan", "german": "Germany", "thai": "Thailand",
    "taiwanese": "Taiwan", "indonesian": "Indonesia", "turkish": "Turkey",
    "italian": "Italy", "french": "France", "portuguese": "Portugal",
    "brazilian": "Brazil", "malaysian": "Malaysia", "moroccan": "Morocco",
    "british": "United Kingdom", "uk": "United Kingdom",
    "hong kong": "Hong Kong",
}


def extract_country_rule_based(query: str) -> str:
    q = query.lower()
    for country in COUNTRIES:
        if country in q:
            normalized = COUNTRY_NORMALIZE.get(country, country.title())
            return normalized
    return ""


def extract_scenario_rule_based(query: str) -> str:
    q = query.lower()
    scores = {scenario: 0 for scenario in SCENARIO_KEYWORDS}
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                scores[scenario] += 1
    return max(scores, key=lambda s: scores[s])


def rephrase_to_hts_rule_based(query: str) -> str:
    q = query.lower()
    for consumer_term, hts_term in HTS_VOCAB.items():
        if consumer_term in q:
            return hts_term
    # strip non-content words and return cleaned query
    stopwords = {"what", "is", "the", "a", "an", "of", "for", "my",
                 "from", "to", "i", "want", "need", "how", "much",
                 "duty", "tariff", "rate", "import", "tax", "china",
                 "mexico", "canada", "vietnam"}
    words = [w for w in q.split() if w not in stopwords]
    return " ".join(words) if words else query


# ── LLM extraction ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a U.S. customs classification assistant.
Extract structured information from the user's trade query.

Respond ONLY with a valid JSON object — no preamble, no markdown, no explanation.
JSON fields:
  product_description  : clean product description (string)
  hts_search_term      : rephrase using official HTS/HTSUS legal vocabulary
                         e.g. "laptop" → "portable automatic data processing machine weighing not more than 10 kg"
                         e.g. "t-shirt" → "knitted cotton shirt for men"
                         e.g. "electric motor" → "AC electric motor"
  origin_country       : country of manufacture/export, or "" if not mentioned
  trade_scenario       : one of: "import_duty", "fta_check", "origin_check"
  analyzer_notes       : one sentence explaining your reasoning

Rules:
  - Use precise HTS/HTSUS legal terminology in hts_search_term
  - If origin_country is China and trade scenario is import_duty,
    note that Section 301 additional tariffs may apply in analyzer_notes
  - Do not invent information not present in the query
"""


def extract_with_llm(raw_query: str) -> dict:
    """
    Extract structured info using OpenAI (cloud) or Ollama (local).
    OpenAI is tried first if OPENAI_API_KEY is set, then Ollama fallback.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": raw_query},
    ]

    content = ""

    # ── try OpenAI first ──────────────────────────────────────────────────────
    if OPENAI_AVAILABLE:
        try:
            client   = _OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=300,
            )
            content = response.choices[0].message.content.strip()
        except Exception as e:
            content = ""

    # ── fallback to Ollama ────────────────────────────────────────────────────
    if not content and OLLAMA_AVAILABLE:
        try:
            response = _ollama.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                options={"temperature": 0.1},
            )
            content = response["message"]["content"].strip()
        except Exception:
            content = ""

    if not content:
        return {"_error": "no LLM available"}

    try:
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$",          "", content)
        parsed  = json.loads(content)
        return {
            "product_description": str(parsed.get("product_description", "")),
            "hts_search_term":     str(parsed.get("hts_search_term", "")),
            "origin_country":      str(parsed.get("origin_country", "")),
            "trade_scenario":      str(parsed.get("trade_scenario", "import_duty")),
            "analyzer_notes":      str(parsed.get("analyzer_notes", "")),
        }
    except Exception as e:
        return {"_error": str(e)}


# ── main node function ────────────────────────────────────────────────────────

def query_analyzer(state: TradeQueryState) -> TradeQueryState:
    """
    LangGraph node — analyzes the raw query and populates extracted fields.
    Falls back to rule-based extraction if Ollama unavailable or fails.
    """
    # strip shipment value annotation added by UI before extracting product
    raw = re.sub(r'\(shipment value[^)]*\)', '', state["raw_query"]).strip()

    extracted = {}
    used_llm  = False

    # try LLM first (OpenAI on cloud, Ollama locally)
    if OPENAI_AVAILABLE or OLLAMA_AVAILABLE:
        result = extract_with_llm(raw)
        if "_error" not in result:
            extracted = result
            used_llm  = True

    # rule-based fallback (or fill any missing fields)
    if not extracted.get("origin_country"):
        extracted["origin_country"] = extract_country_rule_based(raw)

    if not extracted.get("trade_scenario"):
        extracted["trade_scenario"] = extract_scenario_rule_based(raw)

    if not extracted.get("hts_search_term"):
        extracted["hts_search_term"] = rephrase_to_hts_rule_based(raw)

    if not extracted.get("product_description"):
        # strip only query noise words — never strip product nouns
        noise = {
            "what", "is", "the", "a", "an", "of", "for", "my",
            "to", "i", "want", "need", "how", "much", "whats",
            "duty", "tariff", "rate", "import", "importing", "imported",
            "what's", "do", "will", "be", "are", "get", "us",
        }
        words = [w for w in raw.lower().split() if w not in noise]
        # also strip country names from product description
        country_words = {c.lower() for c in COUNTRIES}
        words = [w for w in words if w not in country_words]
        extracted["product_description"] = " ".join(words[:6]).strip() or raw

    if not extracted.get("analyzer_notes"):
        mode = "LLM" if used_llm else "rule-based"
        extracted["analyzer_notes"] = f"Extracted via {mode} analyzer."

    return {
        **state,
        "product_description": extracted["product_description"],
        "hts_search_term":     extracted["hts_search_term"],
        "origin_country":      extracted["origin_country"],
        "trade_scenario":      extracted["trade_scenario"],
        "analyzer_notes":      extracted["analyzer_notes"],
        "chapter_hint":        get_chapter_hint(raw),
    }