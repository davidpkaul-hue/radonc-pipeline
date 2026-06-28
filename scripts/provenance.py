"""Provenance / Audit-Trail des Korpus-Aufbaus — fürs spätere Manuskript.

Rekonstruiert aus den Roh-Caches (refs_topic.jsonl, refs_journal.jsonl) den
kompletten PRISMA-artigen Fluss (Quelle -> Dedup -> Geo-Filter -> final) und
schreibt drei Artefakte nach outputs/ bzw. docs/:

  outputs/tables/corpus_provenance.json   maschinenlesbares Manifest (Stand: jetzt)
  outputs/tables/corpus_runs.jsonl        append-only Historie (1 Zeile je Lauf)
  docs/corpus_provenance.md               manuskriptfertig (Methods + Tabellen)

Die Region-Logik nutzt dieselben Funktionen wie der Merge in radonc_mining,
damit Report und Korpus garantiert konsistent sind.

Aufruf:  python provenance.py        # erzeugt/aktualisiert die Artefakte
"""
from __future__ import annotations

import datetime as _dt
import json
from collections import Counter
from pathlib import Path

import config
import radonc_common as rc
import radonc_mining as m

DACH = ("DE", "AT", "CH")


def _count_lines(path: Path) -> int:
    return sum(1 for _ in rc.read_jsonl(path)) if path.exists() else 0


def build_flow(topic_raw: str = m.TOPIC_RAW,
               journal_raw: str = m.JOURNAL_RAW) -> dict:
    """Rechnet den Fluss exakt aus den Roh-Caches nach (unabhängig vom Merge)."""
    t_path, j_path = config.CACHE / topic_raw, config.CACHE / journal_raw
    raw_topic, raw_journal = _count_lines(t_path), _count_lines(j_path)

    seen: set[str] = set()
    flow = {"gelesen": 0, "duplikate": 0, "geo_verworfen": 0, "behalten": 0}
    by_country = Counter()        # kept: Paper mit >=1 Autor je DACH-Land
    by_year = Counter()           # kept: Paper je Publikationsjahr
    ch_only_kept = 0              # kept, CH ohne DE/AT (rein deutschsprachige CH)
    geo_drop_ch_other = 0        # verworfen wegen rein frz./ital. CH

    for src in (topic_raw, journal_raw):
        for w in rc.read_jsonl(src):
            flow["gelesen"] += 1
            wid = w.get("id")
            if wid in seen:
                flow["duplikate"] += 1
                continue
            seen.add(wid)
            if not rc.is_german_speaking_dach(w):
                flow["geo_verworfen"] += 1
                _, other = rc.ch_region_flags(w)
                geo_drop_ch_other += other
                continue
            flow["behalten"] += 1
            cc = rc.work_countries(w)
            for c in DACH:
                if c in cc:
                    by_country[c] += 1
            if "CH" in cc and "DE" not in cc and "AT" not in cc:
                ch_only_kept += 1
            by_year[w.get("publication_year")] += 1

    return {
        "raw_topic": raw_topic,
        "raw_journal": raw_journal,
        "schnittmenge": raw_topic + raw_journal - len(seen),
        "unique": len(seen),
        "flow": flow,
        "kept_by_country": dict(sorted(by_country.items())),
        "kept_ch_only": ch_only_kept,
        "geo_drop_pure_ch_other": geo_drop_ch_other,
        "kept_by_year": {str(y): n for y, n in sorted(by_year.items(),
                         key=lambda kv: (kv[0] is None, kv[0]))},
    }


def manifest() -> dict:
    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "OpenAlex",
        "openalex_base": config.OPENALEX_BASE,
        "year_range": [config.YEAR_FROM, config.YEAR_TO],
        "countries_filter": config.COUNTRIES,
        "per_page": config.PER_PAGE,
        "queries": {
            "topic_stream": m.topic_filter(),
            "journal_stream": m.journal_filter(),
        },
        "core_journals": config.CORE_JOURNALS,
        "results": build_flow(),
    }


def write_all() -> dict:
    man = manifest()
    # 1) JSON-Manifest (überschrieben)
    rc.write_json(config.TABLES / "corpus_provenance.json", man)
    # 2) append-only Historie
    runlog = config.TABLES / "corpus_runs.jsonl"
    with open(runlog, "a", encoding="utf-8") as f:
        f.write(json.dumps(man, ensure_ascii=False) + "\n")
    # 3) manuskriptfertiges Markdown
    (config.ROOT / "docs" / "corpus_provenance.md").write_text(
        render_markdown(man), encoding="utf-8")
    print(f"[provenance] geschrieben: corpus_provenance.json, corpus_runs.jsonl, "
          f"docs/corpus_provenance.md")
    return man


def render_markdown(man: dict) -> str:
    r = man["results"]
    f = r["flow"]
    y0, y1 = man["year_range"]
    jrows = "\n".join(f"| {name} | `{sid}` |"
                      for name, sid in man["core_journals"].items())
    crows = "\n".join(f"| {c} | {n} |" for c, n in r["kept_by_country"].items())
    yrows = "\n".join(f"| {y} | {n} |" for y, n in r["kept_by_year"].items())
    return f"""# Korpus-Provenance — DACH-Radioonkologie

*Automatisch erzeugt: {man['generated_at']} · Quelle: {man['source']}*

Dieses Dokument protokolliert reproduzierbar, wie der Analyse-Korpus aufgebaut
wurde. Es ist als Grundlage für den Methods-Teil und ein PRISMA-artiges
Flussdiagramm des Manuskripts gedacht.

## 1. Datenquelle & Parameter

- **API:** {man['openalex_base']} (Polite Pool, `mailto`)
- **Zeitfenster:** {y0}–{y1}
- **Länder:** `{man['countries_filter']}` (DE, AT, CH — CH auf deutschsprachige Zentren reduziert)
- **Dokumenttyp:** `article`; Paginierung `cursor`, `per_page={man['per_page']}`

Exakte OpenAlex-Filter:

```
Topic-Stream:   {man['queries']['topic_stream']}
Journal-Stream: {man['queries']['journal_stream']}
```

Kern-Journals (Vereinigungs-Korpus):

| Journal | OpenAlex source-id |
|---|---|
{jrows}

## 2. Aufbau-Fluss (PRISMA-artig)

| Schritt | Paper |
|---|---|
| Stream 1 — Topic (T10358), roh | {r['raw_topic']} |
| Stream 2 — Kern-Journals, roh | {r['raw_journal']} |
| Summe beider Streams | {f['gelesen']} |
| − Duplikate (Schnittmenge Topic ∩ Journal) | −{f['duplikate']} |
| = eindeutige Paper | {r['unique']} |
| − verworfen (rein frz./ital. Schweiz) | −{f['geo_verworfen']} |
| **= finaler DACH-Korpus** | **{f['behalten']}** |

Die Schnittmenge (Paper, die *sowohl* das Topic tragen *als auch* in einem
Kern-Journal erschienen) beträgt {r['schnittmenge']}. Der Journal-Stream trägt
also netto {r['raw_journal'] - r['schnittmenge']} klinische Paper bei, die der
reine Themen-Filter übersehen hätte.

## 3. Regionale Aufschlüsselung (finaler Korpus)

Paper mit mindestens einer Autor:innen-Affiliation im jeweiligen Land
(Mehrfachzuordnung bei Länder-Kooperationen möglich):

| Land | Paper |
|---|---|
{crows}

Davon {r['kept_ch_only']} Paper rein aus der (deutschsprachigen) Schweiz ohne
DE/AT-Beteiligung. Beim Geo-Filter wurden {r['geo_drop_pure_ch_other']} Paper
ausgeschlossen, die ausschließlich an frz./ital. CH-Zentren hingen.

## 4. Verteilung nach Publikationsjahr (finaler Korpus)

| Jahr | Paper |
|---|---|
{yrows}
"""


if __name__ == "__main__":
    write_all()
