"""Zentrale Konfiguration & Pfade für RadOncMining.

Alle Module importieren von hier, damit Pfade und Korpus-Definitionen an
EINER Stelle gepflegt werden. Siehe RadOncMining_Wissensbasis.md Abschnitt 2.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Pfade -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent          # Projektwurzel
SCRIPTS = ROOT / "scripts"
CACHE = ROOT / "cache"                                  # .jsonl / .json
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"

for _d in (CACHE, FIGURES, TABLES):
    _d.mkdir(parents=True, exist_ok=True)

# --- OpenAlex --------------------------------------------------------------
# Polite Pool: mailto reicht im Projekt; api_key nur für höhere Limits.
OPENALEX_BASE = "https://api.openalex.org"
MAILTO = os.environ.get("OPENALEX_MAILTO", "david.kaul@hmu-potsdam.de")
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY")   # optional
PER_PAGE = 200                                          # Paginierung via cursor=*

# Polite Pool: mailto NICHT nur als Query-Param, sondern auch im User-Agent.
USER_AGENT = f"RadOncMining/1.0 (mailto:{MAILTO})"

# Robustheit gegen 429/5xx und Netzabbrüche (siehe radonc_common.paged_stream).
HTTP_TIMEOUT = 60          # Sekunden je Request
MAX_RETRIES = 6            # Versuche je Seite vor Abbruch
BACKOFF_BASE = 2.0         # Wartezeit = BACKOFF_BASE ** versuch (exponentiell)
BACKOFF_CAP = 60.0         # Deckel für die Wartezeit

# --- Korpus-Definitionen (Abschnitt 2 der Wissensbasis) --------------------
TOPIC_RADIOTHERAPY = "T10358"        # Advanced Radiotherapy Techniques
# NICHT Subfield 3108 nehmen (Teilchen-/Beschleunigerphysik verzerrt).

# Korpus-Zeitfenster: bewusst weit zurück (2000), um die akademische
# Prägungsphase heutiger W3-Direktor:innen und Infrastruktur-Events (HIT 2009 …)
# vollständig zu erfassen. Achtung: Metadaten dünnen vor ~2010 aus
# (ORCID erst 2012, DOI-Rückerfassung lückenhaft) -> in späteren Modulen
# dynamisch filtern, NICHT den Download beschneiden.
YEAR_FROM, YEAR_TO = 2000, 2026

# Länder: deutschsprachiger Raum (DACH). DE + AT vollständig; CH wird roh
# mitgezogen, aber in der Bereinigungsschicht auf die deutschsprachigen
# Zentren reduziert (OpenAlex hat keinen Sprach-/Regionenfilter).
COUNTRIES = "de|at|ch"          # OR-Syntax via Pipe (P6: nicht komma = UND!)

# Deutschsprachige Schweizer Radonc-Standorte (Wortgrenzen-Match auf Rohstrings).
CH_GERMAN_CITIES = {
    "zurich", "zürich", "bern", "basel", "aarau", "st. gallen", "st gallen",
    "sankt gallen", "luzern", "lucerne", "chur", "winterthur", "baden",
    "frauenfeld", "liestal", "münsterlingen", "muensterlingen",
}
# Nicht-deutschsprachige CH-Zentren -> ausschließen (frz./ital. Schweiz).
# Achtung: "fribourg"/"freiburg" hier = CH-Fribourg (frz.); das deutsche
# Freiburg i. Br. ist Land DE und vom CH-Filter gar nicht betroffen.
CH_OTHER_CITIES = {
    "geneva", "genève", "geneve", "genf", "lausanne", "fribourg",
    "sion", "neuchâtel", "neuchatel", "bellinzona", "lugano", "locarno",
}

# Ab diesem Jahr ist die Datenlage dicht genug für lückenlose
# Wechsel-/Karriere-Erkennung (Transfermarkt, Chairs). Frühere Jahre nur
# für Kontext/Prägung nutzen, nicht für Spell-basierte Move-Detektion.
DENSE_DATA_FROM = 2010

# 8 Kern-Radioonkologie-Journals (OpenAlex source-IDs) für Vereinigungs-Korpus
CORE_JOURNALS = {
    "Strahlentherapie und Onkologie": "S28603624",
    "Radiotherapy and Oncology": "S144507673",
    "IJROBP": "S110533041",
    "Radiation Oncology": "S42123126",                # BMC (war fehlerhaft dupliziert)
    "Clinical & Translational RO": "S2898297225",
    "Practical Radiation Oncology": "S2764989788",
    "Advances in Radiation Oncology": "S2765008485",
    "Physics & Imaging in RO": "S2898405426",
}
# OR-String für den Filter (dedupliziert, da Journals zusammen einen Key bilden).
CORE_JOURNALS_OR = "|".join(sorted(set(CORE_JOURNALS.values())))

# DKTK als eigene Institution (kein Kind von Heidelberg University) — P1.
INST_DKTK = "I4391767962"

# --- Stadt-Gazetteer deutschsprachiger Radonc-Standorte --------------------
# Kanonische Stadt -> Schreibvarianten (lowercase, dt./engl.). Matching per
# Wortgrenze IRGENDWO im Radonc-Department-String (25% der Strings nennen kein
# Land). Empirisch am Korpus geerdet; per Coverage-Audit erweiterbar.
CITY_GAZETTEER = {
    # Deutschland — Unikliniken + große Zentren
    "Heidelberg": ["heidelberg"],
    "Mannheim": ["mannheim"],                       # Vorrang vor Heidelberg (UMM)
    "München": ["münchen", "munich", "muenchen", "munchen"],
    "Neuherberg": ["neuherberg"],                   # Helmholtz München
    "Dresden": ["dresden"],
    "Berlin": ["berlin"],
    "Erlangen": ["erlangen"],
    "Freiburg": ["freiburg"],
    "Tübingen": ["tübingen", "tuebingen", "tubingen"],
    "Essen": ["essen"],
    "Hamburg": ["hamburg"],
    "Marburg": ["marburg"],
    "Kiel": ["kiel"],
    "Würzburg": ["würzburg", "wuerzburg", "wurzburg"],
    "Münster": ["münster", "muenster", "munster"],
    "Hannover": ["hannover", "hanover"],
    "Göttingen": ["göttingen", "goettingen", "gottingen"],
    "Bonn": ["bonn"],
    "Aachen": ["aachen"],
    "Köln": ["köln", "koeln", "cologne"],
    "Regensburg": ["regensburg"],
    "Leipzig": ["leipzig"],
    "Lübeck": ["lübeck", "luebeck", "lubeck"],
    "Homburg": ["homburg"],                         # Homburg/Saar
    "Frankfurt": ["frankfurt"],
    "Jena": ["jena"],
    "Darmstadt": ["darmstadt"],
    "Gießen": ["gießen", "giessen"],
    "Mainz": ["mainz"],
    "Offenbach": ["offenbach"],
    "Rostock": ["rostock"],
    "Halle": ["halle"],
    "Magdeburg": ["magdeburg"],
    "Greifswald": ["greifswald"],
    "Ulm": ["ulm"],
    "Augsburg": ["augsburg"],
    "Bochum": ["bochum"],
    "Düsseldorf": ["düsseldorf", "duesseldorf", "dusseldorf"],
    "Nürnberg": ["nürnberg", "nuremberg", "nuernberg", "nurnberg"],
    "Stuttgart": ["stuttgart"],
    "Karlsruhe": ["karlsruhe"],
    "Bremen": ["bremen"],
    "Wiesbaden": ["wiesbaden"],
    "Koblenz": ["koblenz"],
    "Oldenburg": ["oldenburg"],
    "Braunschweig": ["braunschweig", "brunswick"],
    "Kassel": ["kassel"],
    "Trier": ["trier"],
    "Saarbrücken": ["saarbrücken", "saarbruecken", "saarbrucken"],
    "Neuruppin": ["neuruppin"],
    "Landshut": ["landshut"],
    "Lemgo": ["lemgo"],
    "Gummersbach": ["gummersbach"],
    # Österreich
    "Wien": ["wien", "vienna"],
    "Innsbruck": ["innsbruck"],
    "Graz": ["graz"],
    "Salzburg": ["salzburg"],
    "Linz": ["linz"],
    "Klagenfurt": ["klagenfurt"],
    "Feldkirch": ["feldkirch"],
    # Deutschsprachige Schweiz
    "Zürich": ["zürich", "zurich", "zuerich"],
    "Bern": ["bern", "berne"],
    "Basel": ["basel"],
    "Aarau": ["aarau"],
    "St. Gallen": ["st. gallen", "st gallen", "st.gallen", "sankt gallen"],
    "Luzern": ["luzern", "lucerne"],
    "Chur": ["chur"],
    "Winterthur": ["winterthur"],
    "Villigen": ["villigen", "paul scherrer"],       # PSI (Strings lassen oft "Villigen" weg)
    # Nicht-Uni-Standorte / kleinere Zentren (aus Coverage-Audit ergänzt)
    "Bielefeld": ["bielefeld"],
    "Soest": ["soest"],
    "Schweinfurt": ["schweinfurt"],
    "Chemnitz": ["chemnitz"],
    "Coburg": ["coburg"],
    "Dessau": ["dessau"],
    "Wiener Neustadt": ["wiener neustadt", "wr. neustadt", "wr neustadt"],  # MedAustron
    "Kaiserslautern": ["kaiserslautern"],
    "Fulda": ["fulda"],
    "Passau": ["passau"],
    "Singen": ["singen"],
    "Görlitz": ["görlitz", "goerlitz"],
    "Zwickau": ["zwickau"],
    "Hildesheim": ["hildesheim"],
    "Osnabrück": ["osnabrück", "osnabrueck"],
    "Recklinghausen": ["recklinghausen"],
    "Bayreuth": ["bayreuth"],
    "Bamberg": ["bamberg"],
    "Ravensburg": ["ravensburg"],
    "Heilbronn": ["heilbronn"],
    "Esslingen": ["esslingen"],
    "Reutlingen": ["reutlingen"],
    "Minden": ["minden"],
    "Gera": ["gera"],
}

# Wenn beide in EINEM String stehen, gewinnt Mannheim (UMM = Med. Fak.
# Mannheim der Uni Heidelberg) — sonst würde Mannheim Heidelberg zugeschlagen.
CITY_PRIORITY = {"Heidelberg": ["Mannheim"]}

# Land je kanonischer Stadt (für Färbung/Aufschlüsselung). Rest = DE.
AT_CITIES = {"Wien", "Innsbruck", "Graz", "Salzburg", "Linz", "Klagenfurt",
             "Feldkirch", "Wiener Neustadt"}
CH_CITIES = {"Zürich", "Bern", "Basel", "Aarau", "St. Gallen", "Luzern",
             "Chur", "Winterthur", "Villigen"}


def country_of(city: str) -> str:
    if city in AT_CITIES:
        return "AT"
    if city in CH_CITIES:
        return "CH"
    return "DE"


# Neue Länder (ehem. DDR) für Ost-West-Vergleich. Berlin = geteilt -> separat.
EAST_CITIES = {"Dresden", "Leipzig", "Chemnitz", "Zwickau", "Görlitz", "Halle",
               "Magdeburg", "Dessau", "Jena", "Gera", "Rostock", "Greifswald",
               "Neuruppin"}


def region_of(city: str) -> str | None:
    """Ost / West / Berlin für deutsche Städte; None für AT/CH."""
    if city in EAST_CITIES:
        return "Ost"
    if city == "Berlin":
        return "Berlin"
    return "West" if country_of(city) == "DE" else None
