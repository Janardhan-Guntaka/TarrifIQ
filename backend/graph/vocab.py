"""HTS vocabulary and rule-based query extractors (migrated from V1 query_analyzer)."""

# â”€â”€ HTS vocabulary map (rule-based fallback) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# consumer term â†’ HTS legal term  (longest match wins â€” order matters)
# Covers top 12 SME import chapters: 33,39,44,61-64,73,84,85,90,94,95
HTS_VOCAB: dict[str, str] = {

    # â”€â”€ Ch 84 â€” Machinery / computers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 85 â€” Electronics / electrical â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 61-62 â€” Apparel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 63 â€” Home textiles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 64 â€” Footwear â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 39 â€” Plastics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 44 â€” Wood products â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 73 â€” Steel articles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 94 â€” Furniture / lighting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 95 â€” Toys / sports / games â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 33 â€” Cosmetics / personal care â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Ch 90 â€” Optical / instruments â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ trade scenario keywords â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# â”€â”€ chapter hint map â€” product keyword â†’ likely HTS chapter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Used to pre-filter vector search, avoiding cross-chapter confusion
# e.g. "electric motor" must search ch85 not ch87 (motorcycles)
CHAPTER_HINTS: dict[str, str] = {
    # ch 84 â€” machinery
    "laptop": "84", "computer": "84", "pump": "84", "compressor": "84",
    "engine": "84", "turbine": "84", "conveyor": "84", "forklift": "84",
    "refrigerator": "84", "washing machine": "84", "dishwasher": "84",
    "heat exchanger": "84", "printer": "84",
    # ch 85 â€” electronics / electrical
    "electric motor": "85", "motor": "85", "transformer": "85",
    "smartphone": "85", "phone": "85", "led": "85", "lamp": "85",
    "battery": "85", "charger": "85", "solar panel": "85",
    "headphones": "85", "earbuds": "85", "speaker": "85",
    "circuit board": "85", "pcb": "85", "inverter": "85",
    "router": "85", "switch": "85", "camera": "85",
    # ch 61 â€” knitted apparel
    "t-shirt": "61", "tshirt": "61", "hoodie": "61", "sweater": "61",
    "knitwear": "61", "leggings": "61", "socks": "61", "underwear": "61",
    # ch 62 â€” woven apparel
    "shirt": "62", "trousers": "62", "jeans": "62", "jacket": "62",
    "suit": "62", "dress": "62", "blouse": "62", "coat": "62",
    # ch 39 â€” plastics
    "plastic": "39", "polyethylene": "39", "polypropylene": "39",
    "silicone": "39", "pvc": "39",
    # ch 94 â€” furniture / lighting
    "sofa": "94", "chair": "94", "desk": "94", "table": "94",
    "mattress": "94", "wardrobe": "94", "cabinet": "94",
    # ch 64 â€” footwear
    "shoes": "64", "sneakers": "64", "boots": "64", "sandals": "64",
    # ch 73 â€” steel
    "steel pipe": "73", "pipe fitting": "73", "bolt": "73", "screw": "73",
    # ch 44 â€” wood
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

# â”€â”€ country extraction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


