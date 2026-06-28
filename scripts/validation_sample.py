"""Validierungs-Stichprobe — Goldstandard fürs Methodenpaper (Precision/Recall).

Zieht eine reproduzierbare Zufallsstichprobe von Papern und legt je Paper den
LETZTAUTOR vor: dessen Roh-Affiliationszeilen (zum manuellen Lesen), plus die
Stadt-Zuordnung dreier Verfahren —

  strict : g.last_author_cities          (nur Radonc-Zeilen, strikt)
  gated  : g.last_author_cities_gated    (strikt + Senior-Fallback)
  naive  : Gazetteer über die OpenAlex-INSTITUTIONS-Tags (ohne DEPT-Filter,
           ohne DKTK-Guard, ohne Mannheim-Vorrang) — der „naive" Baseline,
           der die Konsortiums-Über-Zuordnung sichtbar macht.

Die Spalte `gold_cities` bleibt LEER und wird manuell ausgefüllt: die/der
Kodierende liest `last_author_raw_affils` und trägt die korrekte(n)
deutschsprachige(n) Radonc-Stadt/Städte ein (kanonische Namen, mit `;` getrennt;
`none` wenn ausländisch / frz.-ital. CH / fachfremd / keine).

Schreibt:  outputs/validation/validation_sample.csv   (zum Kodieren)

Aufruf:  python validation_sample.py [N]      # Default N=200, Seed fix
"""
from __future__ import annotations

import csv
import random
import sys

import config
import radonc_common as rc
import radonc_geo as g

SEED = 42
DEFAULT_N = 200
VALID = config.OUTPUTS / "validation"


def naive_institution_cities(authorship: dict) -> set[str]:
    """Naiver Baseline: Gazetteer-Match über die Institutions-Tags des Autors.

    Bewusst OHNE DEPT/EXCL, OHNE DKTK-Guard, OHNE Mannheim-Vorrang — so wie eine
    naive Auswertung die disambiguierten Institution-Objekte nutzen würde.
    """
    cities: set[str] = set()
    for inst in authorship.get("institutions") or []:
        name = (inst.get("display_name") or "").lower()
        for canon, regs in g._CITY_RE.items():
            if any(r.search(name) for r in regs):
                cities.add(canon)
    return cities


def main(n: int = DEFAULT_N) -> None:
    VALID.mkdir(parents=True, exist_ok=True)
    senior_ids, senior_keys = g.load_senior_set()

    works = list(rc.read_jsonl("refs.jsonl"))
    random.seed(SEED)
    random.shuffle(works)

    rows = []
    for w in works:
        la = rc.last_authorship(w)
        if not la:
            continue
        au = la.get("author") or {}
        raw = la.get("raw_affiliation_strings") or []
        strict = sorted(g.last_author_cities(w))
        gated = sorted(g.last_author_cities_gated(w, senior_ids, senior_keys)[0])
        naive = sorted(naive_institution_cities(la))
        rows.append({
            "work_id": w.get("id"),
            "year": w.get("publication_year"),
            "title": (w.get("title") or "")[:120],
            "last_author_name": au.get("display_name"),
            "last_author_id": au.get("id"),
            "last_author_raw_affils": " || ".join(raw),
            "strict_cities": ";".join(strict),
            "gated_cities": ";".join(gated),
            "naive_cities": ";".join(naive),
            "gold_cities": "",          # <- manuell ausfüllen
            "notes": "",
        })
        if len(rows) >= n:
            break

    out = VALID / "validation_sample.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"[validation] {len(rows)} Paper (Seed {SEED}) -> {out}")
    print("[validation] Bitte Spalte 'gold_cities' manuell ausfüllen "
          "(kanonische Stadtnamen, ';'-getrennt; 'none' wenn keine).")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N
    main(n)
