"""Ortszuordnung — Paper -> deutschsprachige Radonc-Stadt.

Grundsätze (siehe Wissensbasis Abschnitt 4/5):
- Stadt aus `raw_affiliation_strings`, NICHT aus authorships.institutions (P1/P2).
- Nur Radonc-Department-Zeilen (DEPT/EXCL) liefern eine Stadt -> filtert
  DKTK-/DKFZ-Konsortiumszeilen (Fall-3-Phantomstädte) heraus.
- Wortgrenzen-Match (P5: \\bfreiburg\\b matcht nicht "Freiburgstrasse").
- Mannheim hat Vorrang vor Heidelberg im selben String (UMM).

Zähleinheiten:
- Letztautor-Städte: Städte aus den Radonc-Strings des Letztautors. Bei echter
  Doppelberufung zählen BEIDE Städte ganz (Nutzer-Entscheidung).
- Präsenz-Städte: Menge aller Radonc-Städte über alle Autor:innen.

Aufruf:  python radonc_geo.py            # Coverage-Audit der Zuordnung
"""
from __future__ import annotations

import re
from collections import Counter

import config
import radonc_common as rc

# Vorkompilierte Wortgrenzen-Regexe je Stadt-Variante.
_CITY_RE = {
    canon: [re.compile(rf"\b{re.escape(v)}\b") for v in variants]
    for canon, variants in config.CITY_GAZETTEER.items()
}


# Marker der DKTK-Konsortiums-Expansion (P1). NICHT bloßes "dkfz"/"krebsforschung"
# — das ist die echte Heidelberg-Institution und soll erhalten bleiben.
_CONSORTIUM = ("dktk", "german cancer consortium", "partner site", "partner-site")


def cities_in_string(s: str) -> set[str]:
    """Alle Gazetteer-Städte in EINEM String (Wortgrenze), mit Mannheim-Vorrang.

    P1-Schutz: Enthält die Zeile einen DKTK-Konsortiums-Marker UND mehrere
    Städte, zählt nur die ZUERST genannte (das eigene Department; die DKTK-
    Zentrale wird typischerweise hinten angehängt -> Phantom-Stadt fällt weg).
    """
    low = s.lower()
    starts = {}
    for canon, regs in _CITY_RE.items():
        pos = min((m.start() for r in regs if (m := r.search(low))), default=None)
        if pos is not None:
            starts[canon] = pos
    found = set(starts)
    # Prioritäts-Regeln (z.B. Mannheim verdrängt Heidelberg im selben String).
    for loser, winners in config.CITY_PRIORITY.items():
        if loser in found and any(w in found for w in winners):
            found.discard(loser)
            starts.pop(loser, None)
    # DKTK-Konsortiums-Zeile mit mehreren Städten -> nur die erste behalten.
    if len(found) > 1 and any(m in low for m in _CONSORTIUM):
        first = min(found, key=lambda c: starts[c])
        found = {first}
    return found


def author_cities(authorship: dict) -> set[str]:
    """Radonc-Städte EINES Autors aus seinen Radonc-Department-Strings."""
    cities: set[str] = set()
    for s in authorship.get("raw_affiliation_strings") or []:
        if rc.is_radonc_affiliation(s):
            cities |= cities_in_string(s)
    return cities


def _excl(s: str) -> bool:
    low = s.lower()
    return any(x in low for x in rc.EXCL)


def author_cities_fallback(authorship: dict) -> set[str]:
    """Fallback-Städte: aus JEDEM nicht-EXCL-String (auch ohne Radonc-Wort).

    EXCL-Gate hält Urologie/Neuroradiologie/Nuklearmedizin draußen, lässt aber
    'Universitätsklinikum Tübingen' ohne Dept-Wort durch.
    """
    cities: set[str] = set()
    for s in authorship.get("raw_affiliation_strings") or []:
        if not _excl(s):
            cities |= cities_in_string(s)
    return cities


def last_author_cities(work: dict) -> set[str]:
    """Städte des Letztautors aus seinen Radonc-Strings (strikt)."""
    la = rc.last_authorship(work)
    return author_cities(la) if la else set()


def last_author_cities_ext(work: dict) -> tuple[set[str], bool]:
    """Letztautor-Städte mit (ungegatetem) Fallback. Rückgabe: (städte, war_fallback).

    Primär die strikten Radonc-Städte; nur wenn leer, der EXCL-gesicherte
    Fallback. Das Flag erlaubt die Sensitivitätsanalyse (strikt vs. erweitert).
    """
    strict = last_author_cities(work)
    if strict:
        return strict, False
    la = rc.last_authorship(work)
    return (author_cities_fallback(la) if la else set()), True


# --- Personen-gegateter Fallback (Senior-Set) ------------------------------
def _author_key(authorship: dict) -> tuple[str | None, tuple[str, str]]:
    """Identität eines Autors: (OpenAlex-id, name_key) — gegen Profil-Splits (P3)."""
    au = authorship.get("author") or {}
    nm = au.get("display_name") or authorship.get("raw_author_name") or ""
    return au.get("id"), rc.name_key(nm)


def build_radonc_senior_set(src: str = "refs.jsonl", min_strict: int = 2,
                            cache: str = "radonc_seniors.json") -> dict:
    """Set 'bekannter Radonc-Senioren': Personen mit >= min_strict strikten
    Radonc-Letztautor-Papern. Robust per author-id UND name_key. Wird gecacht.
    """
    from collections import Counter
    by_id, by_key = Counter(), Counter()
    for w in rc.read_jsonl(src):
        if not last_author_cities(w):       # nur strikte Radonc-Letztautoren
            continue
        la = rc.last_authorship(w)
        if not la:
            continue
        aid, key = _author_key(la)
        if aid:
            by_id[aid] += 1
        by_key[key] += 1
    seniors = {
        "ids": sorted(i for i, c in by_id.items() if c >= min_strict),
        "keys": sorted("|".join(k) for k, c in by_key.items() if c >= min_strict),
        "min_strict": min_strict,
    }
    rc.write_json(cache, seniors)
    return seniors


def load_senior_set(cache: str = "radonc_seniors.json") -> tuple[set, set]:
    """Lädt das Senior-Set; baut es automatisch, falls der Cache fehlt."""
    if not (config.CACHE / cache).exists():
        print("[geo] Senior-Set-Cache fehlt -> baue neu …")
        build_radonc_senior_set(cache=cache)
    s = rc.read_json(cache)
    return set(s["ids"]), set(s["keys"])


def is_known_senior(authorship: dict, senior_ids: set, senior_keys: set) -> bool:
    aid, key = _author_key(authorship)
    return (aid in senior_ids) or ("|".join(key) in senior_keys)


def last_author_cities_gated(work: dict, senior_ids: set, senior_keys: set
                             ) -> tuple[set[str], str]:
    """Personen-gegatetes Letztautor-Maß. Rückgabe: (städte, modus).

    modus: 'strict' | 'fallback' (nur falls Letztautor bekannte:r Radonc-Senior:in)
    | 'none'. Entfernt fachfremde Senioren (Radiologie, IAEA …) aus dem Fallback.
    """
    strict = last_author_cities(work)
    if strict:
        return strict, "strict"
    la = rc.last_authorship(work)
    if la and is_known_senior(la, senior_ids, senior_keys):
        c = author_cities_fallback(la)
        if c:
            return c, "fallback"
    return set(), "none"


def presence_cities(work: dict) -> set[str]:
    """Alle Radonc-Städte über sämtliche Autor:innen des Papers."""
    cities: set[str] = set()
    for a in work.get("authorships", []):
        cities |= author_cities(a)
    return cities


# --- Coverage-Audit --------------------------------------------------------
def coverage_audit(src: str = "refs.jsonl", n_residual: int = 25) -> dict:
    """Prüft die Zuordnungsqualität, BEVOR die Hegemonie-Rangliste gebaut wird."""
    total = 0
    strict = strict_multi = 0
    fb_added = fb_multi = 0
    none_at_all = 0
    pres_assigned = 0
    residual = Counter()        # Radonc-Strings (DACH) ohne Stadt-Match

    for w in rc.read_jsonl(src):
        total += 1
        cities, was_fb = last_author_cities_ext(w)
        if cities and not was_fb:
            strict += 1
            if len(cities) > 1:
                strict_multi += 1
        elif cities and was_fb:
            fb_added += 1
            if len(cities) > 1:
                fb_multi += 1
        else:
            none_at_all += 1
            la = rc.last_authorship(w) or {}
            for s in la.get("raw_affiliation_strings") or []:
                sl = s.lower()
                if (rc.is_radonc_affiliation(s) and not cities_in_string(s)
                        and any(x in sl for x in ("germany", "austria",
                        "switzerland", "deutschland", "österreich", "schweiz"))):
                    residual[s.strip()[:90]] += 1
        if presence_cities(w):
            pres_assigned += 1

    def pct(x):
        return round(100 * x / total, 1) if total else 0.0

    ext = strict + fb_added
    print(f"Korpus: {total} Paper")
    print(f"Letztautor STRIKT (Radonc-Dept) : {strict} ({pct(strict)}%)  "
          f"Doppel-Stadt: {strict_multi}")
    print(f"+ Fallback (EXCL-gesichert)     : +{fb_added} ({pct(fb_added)}%)  "
          f"Doppel-Stadt: {fb_multi}")
    print(f"= ERWEITERT gesamt              : {ext} ({pct(ext)}%)")
    print(f"weder noch (echte Lücke)        : {none_at_all} ({pct(none_at_all)}%)")
    print(f"Präsenz zugeordnet              : {pres_assigned} ({pct(pres_assigned)}%)")
    print(f"\nTop {n_residual} unzuordenbare DACH-Radonc-Strings (Gazetteer-Lücken):")
    for s, c in residual.most_common(n_residual):
        print(f"  {c:4}  {s}")
    return {"total": total, "strict": strict, "fallback_added": fb_added,
            "extended": ext, "none": none_at_all, "pres_assigned": pres_assigned,
            "residual_top": residual.most_common(n_residual)}


if __name__ == "__main__":
    coverage_audit()
