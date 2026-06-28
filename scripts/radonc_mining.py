"""Modul 1 — Korpus-Aufbau (Vereinigungs-Korpus).

Baut den Vereinigungs-Korpus  (Topic T10358  ODER  8 Kern-Journals),
DACH (de|at|ch), article, 2000-2026, inkl. referenced_works.

OpenAlex verknüpft verschiedene Filter-Kategorien IMMER mit UND. Die
Vereinigung (OR über Topic vs. Journal) gibt es server-seitig nicht ->
DUAL-STREAM: zwei getrennte Abfragen, je eigene Rohdatei + eigener
Checkpoint (unabhängig wiederaufsetzbar), danach lokaler Merge mit
Dedup über work-id und DACH-Sprachfilter.

  cache/refs_topic.jsonl    Stream 1 (Topic), roh
  cache/refs_journal.jsonl  Stream 2 (Journals), roh
  cache/refs.jsonl          Merge: dedupliziert + deutschsprachig

Aufruf:  python radonc_mining.py           # laden + mergen (resume-fähig)
         python radonc_mining.py --fresh   # Checkpoints ignorieren, neu laden
         python radonc_mining.py --merge   # nur neu mergen (kein Download)
"""
from __future__ import annotations

import sys

import config
import radonc_common as rc

# Felder schlank halten -> kleinere Antworten, schnellere Paginierung.
SELECT = ",".join([
    "id", "publication_year", "type",
    "authorships", "referenced_works",
    "primary_topic", "primary_location",
])

_COMMON = (
    f"authorships.countries:{config.COUNTRIES},"       # de|at|ch (OR)
    f"type:article,"
    f"publication_year:{config.YEAR_FROM}-{config.YEAR_TO}"
)

TOPIC_RAW = "refs_topic.jsonl"
JOURNAL_RAW = "refs_journal.jsonl"


def topic_filter() -> str:
    """Stream 1: alle Artikel des Radioonkologie-Topics."""
    return f"topics.id:{config.TOPIC_RADIOTHERAPY},{_COMMON}"


def journal_filter() -> str:
    """Stream 2: alle Artikel aus den 8 klinischen Kern-Journals (OR)."""
    return f"primary_location.source.id:{config.CORE_JOURNALS_OR},{_COMMON}"


# --- Download --------------------------------------------------------------
def build_union_corpus(resume: bool = True) -> tuple[int, int]:
    """Lädt beide Streams robust in JE EIGENE Rohdatei (eigener Checkpoint)."""
    print("== Stream 1: Topic-Korpus ==")
    n_topic = rc.paged_stream("works", topic_filter(), TOPIC_RAW,
                              select=SELECT, resume=resume)
    print("== Stream 2: Journal-Korpus ==")
    n_journal = rc.paged_stream("works", journal_filter(), JOURNAL_RAW,
                                select=SELECT, resume=resume)
    return n_topic, n_journal


# --- Merge + Bereinigung ---------------------------------------------------
def merge_filter_dedup(dst: str = "refs.jsonl") -> dict:
    """Mergt beide Rohdateien: Dedup über work-id + DACH-Sprachfilter.

    Zählt sauber getrennt: Duplikate (ID in beiden Streams) vs. Geo-Drops
    (rein frz./ital. CH). Rückgabe: Kennzahlen-Dict.
    """
    seen: set[str] = set()
    stats = {"gelesen": 0, "duplikate": 0, "geo_verworfen": 0, "behalten": 0}

    def merged():
        for src in (TOPIC_RAW, JOURNAL_RAW):
            for w in rc.read_jsonl(src):
                stats["gelesen"] += 1
                wid = w.get("id")
                if wid in seen:
                    stats["duplikate"] += 1
                    continue
                seen.add(wid)
                if not rc.is_german_speaking_dach(w):
                    stats["geo_verworfen"] += 1
                    continue
                stats["behalten"] += 1
                yield w

    rc.write_jsonl(dst, merged())
    print(f"[Modul 1] Merge fertig -> {config.CACHE / dst}")
    print(f"  gelesen={stats['gelesen']}  duplikate={stats['duplikate']}  "
          f"geo_verworfen={stats['geo_verworfen']}  behalten={stats['behalten']}")
    return stats


if __name__ == "__main__":
    if "--merge" not in sys.argv:
        build_union_corpus(resume="--fresh" not in sys.argv)
    merge_filter_dedup()
    # Provenance/Audit-Trail fürs Manuskript automatisch mitschreiben.
    import provenance
    provenance.write_all()
