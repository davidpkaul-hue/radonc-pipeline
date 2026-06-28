"""Wiederverwendbare Bausteine für RadOncMining.

Bündelt die in der Wissensbasis (Abschnitt 4 & 5) erarbeiteten Helfer:
OpenAlex-Client mit cursor-Paginierung, JSONL-Cache, Radonc-Department-Filter,
Orts-/Namens-Deduplizierung. Module wie radonc_mining.py bauen hierauf auf.
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Iterable, Iterator

import requests

import config


# --- OpenAlex-Client -------------------------------------------------------
# Eine wiederverwendete Session mit Polite-Pool-User-Agent (mailto im Header).
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": config.USER_AGENT})


def _params(extra: dict) -> dict:
    p = {"mailto": config.MAILTO}
    if config.OPENALEX_API_KEY:
        p["api_key"] = config.OPENALEX_API_KEY
    p.update(extra)
    return p


def _get(endpoint: str, extra: dict) -> dict:
    """GET mit Exponential-Backoff bei 429/5xx und Netzfehlern.

    Wartezeit wächst exponentiell (BACKOFF_BASE ** versuch), gedeckelt und mit
    etwas Jitter. Bei 429 wird ein vorhandener Retry-After-Header bevorzugt.
    """
    url = f"{config.OPENALEX_BASE}/{endpoint}"
    last_exc: Exception | None = None
    for attempt in range(config.MAX_RETRIES):
        try:
            r = _SESSION.get(url, params=_params(extra), timeout=config.HTTP_TIMEOUT)
            if r.status_code in (429, 500, 502, 503, 504):
                wait = _backoff(attempt, r.headers.get("Retry-After"))
                print(f"  [retry] HTTP {r.status_code}, warte {wait:.1f}s "
                      f"(Versuch {attempt + 1}/{config.MAX_RETRIES})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            wait = _backoff(attempt, None)
            print(f"  [retry] {type(e).__name__}, warte {wait:.1f}s "
                  f"(Versuch {attempt + 1}/{config.MAX_RETRIES})")
            time.sleep(wait)
    raise RuntimeError(
        f"OpenAlex-Request endgültig fehlgeschlagen nach "
        f"{config.MAX_RETRIES} Versuchen: {endpoint} {extra}"
    ) from last_exc


def _backoff(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    wait = min(config.BACKOFF_BASE ** attempt, config.BACKOFF_CAP)
    return wait + random.uniform(0, 0.5)   # Jitter gegen Thundering Herd


def paged(endpoint: str, filters: str, select: str | None = None,
          per_page: int = config.PER_PAGE, sleep: float = 0.0,
          start_cursor: str = "*") -> Iterator[tuple[list[dict], str | None]]:
    """Iteriert Endpunkt seitenweise via cursor=* (nicht page=).

    Liefert je Seite (records, next_cursor). next_cursor ist der Cursor für die
    FOLGENDE Seite (None am Ende) -> ideal fürs Checkpointing.
    ACHTUNG (P6): kommaseparierte Filter = UND; "A+B" in einem Key = ODER.
    author_position ist KEIN Top-Level-Filter -> client-seitig bestimmen.
    """
    cursor = start_cursor
    while cursor:
        extra = {"filter": filters, "per-page": per_page, "cursor": cursor}
        if select:
            extra["select"] = select
        data = _get(endpoint, extra)
        records = data.get("results", [])
        cursor = data.get("meta", {}).get("next_cursor")
        yield records, cursor
        if sleep:
            time.sleep(sleep)


def paged_stream(endpoint: str, filters: str, out: str | Path,
                 select: str | None = None, per_page: int = config.PER_PAGE,
                 sleep: float = 0.1, resume: bool = True) -> int:
    """Lädt einen kompletten Korpus robust und inkrementell in eine JSONL.

    - Schreibt JEDE Seite sofort per Append -> Absturz = nur letzte Seite verloren.
    - Speichert nach jeder Seite den next_cursor in <out>.ckpt -> Wiederaufsetzen.
    - resume=True: vorhandenen Checkpoint fortsetzen (Append), sonst frisch starten.
    Dedup über work-id passiert downstream (seltene Doppel-Seite bei Crash möglich).
    Rückgabe: Anzahl in DIESEM Lauf geschriebener Datensätze.
    """
    out = config.CACHE / out if not Path(out).is_absolute() else Path(out)
    ckpt = out.with_suffix(out.suffix + ".ckpt")

    cursor = "*"
    mode = "w"
    if resume and ckpt.exists():
        saved = ckpt.read_text(encoding="utf-8").strip()
        if saved == "DONE":
            print(f"[stream] {out.name} bereits vollständig (Checkpoint DONE).")
            return 0
        if saved:
            cursor, mode = saved, "a"
            print(f"[stream] Setze {out.name} ab Checkpoint fort.")

    n = 0
    with open(out, mode, encoding="utf-8") as f:
        for records, next_cursor in paged(endpoint, filters, select, per_page,
                                          sleep, start_cursor=cursor):
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
            f.flush()
            ckpt.write_text(next_cursor or "DONE", encoding="utf-8")
            print(f"  [stream] +{len(records)} (gesamt dieser Lauf: {n})")
    print(f"[stream] fertig: {n} Datensätze -> {out}")
    return n


def group_by(endpoint: str, filters: str, key: str) -> list[dict]:
    """OpenAlex group_by-Aggregat (eine Anfrage, mit Retry)."""
    data = _get(endpoint, {"filter": filters, "group-by": key})
    return data.get("group_by", [])


# --- JSONL/JSON-Cache ------------------------------------------------------
def write_jsonl(path: str | Path, rows: Iterable[dict]) -> int:
    path = config.CACHE / path if not Path(path).is_absolute() else Path(path)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: str | Path) -> Iterator[dict]:
    path = config.CACHE / path if not Path(path).is_absolute() else Path(path)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: str | Path, obj) -> None:
    path = config.CACHE / path if not Path(path).is_absolute() else Path(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_json(path: str | Path):
    path = config.CACHE / path if not Path(path).is_absolute() else Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- Radonc-Department-Filter (Wissensbasis 4.3) ---------------------------
# Stämme (Teilstrings) statt Vollformen -> deckt dt./engl. Varianten ab.
DEPT = [
    "radiation oncolog", "radiation therap", "radiotherap",   # incl. Radiotherapie
    "radiooncolog", "radio-oncolog", "radio oncolog",         # engl. zusammen/Bindestrich
    "strahlenther", "strahlenheilkunde", "strahlenklinik",    # dt. Klinik-Namen
    "radioonkolog", "radio-onkolog", "radiation medicine",
    "particle therap", "proton therap", "proton beam",
    "hadron therap", "heavy ion", "schwerionen",
    "medical physics", "medizinische physik", "radiation physics",
    "strahlenphysik", "oncoray", "medaustron", "paul scherrer",
]
EXCL = [
    "neuroradiolog", "diagnostic radiolog", "diagnostische radiologie",
    "interventional radiolog", "nuclear medicine", "nuklearmedizin",
    "urolog", "department of radiology", "institute of radiology",
    "klinik für radiologie",
]


def is_radonc_affiliation(raw: str) -> bool:
    """True, wenn ein raw_affiliation_string zu einem Radonc-Department gehört."""
    s = raw.lower()
    if any(x in s for x in EXCL):
        return False
    return any(x in s for x in DEPT)


# --- Orts- & Namens-Deduplizierung (Wissensbasis 4.1, 4.9, 4.12) -----------
_FOREIGN = ("switzerland", "austria", "netherlands", "france", "belgium",
            "denmark", "usa", "united states", "united kingdom")


def city_in_string(raw: str, cities: Iterable[str]) -> str | None:
    """Wortgrenzen-Match einer deutschen Stadt; Auslandsstrings ausgeschlossen (P5)."""
    s = raw.lower()
    if any(f in s for f in _FOREIGN):
        return None
    for city in cities:
        if re.search(rf"\b{re.escape(city.lower())}\b", s):
            return city
    return None


def name_key(display_name: str) -> tuple[str, str]:
    """(Nachname, Erst-Initial) für Profil-Split-Dedup (P3)."""
    parts = display_name.strip().split()
    if not parts:
        return ("", "")
    last = parts[-1].lower()
    first_initial = parts[0][:1].lower()
    return (last, first_initial)


def _raw_strings(work: dict) -> Iterator[str]:
    for a in work.get("authorships", []):
        for s in a.get("raw_affiliation_strings", []) or []:
            yield s


def work_countries(work: dict) -> set[str]:
    """Alle Länder-Codes (ISO-2) eines Papers aus authorships + institutions."""
    cc: set[str] = set()
    for a in work.get("authorships", []):
        cc.update(a.get("countries") or [])
        for inst in a.get("institutions", []):
            if inst.get("country_code"):
                cc.add(inst["country_code"])
    return cc


def ch_region_flags(work: dict) -> tuple[bool, bool]:
    """(hat_deutschsprachige_CH, hat_frz/ital_CH) anhand der Rohstrings."""
    de_ch = other_ch = False
    for raw in _raw_strings(work):
        s = raw.lower()
        if any(re.search(rf"\b{re.escape(c)}\b", s) for c in config.CH_GERMAN_CITIES):
            de_ch = True
        if any(re.search(rf"\b{re.escape(c)}\b", s) for c in config.CH_OTHER_CITIES):
            other_ch = True
    return de_ch, other_ch


def is_german_speaking_dach(work: dict) -> bool:
    """True, wenn das Paper im deutschsprachigen Raum (DE/AT/dt. CH) verortet ist.

    DE- oder AT-Affiliation -> immer drin. Reine CH-Paper nur, wenn mindestens
    eine deutschsprachige CH-Stadt vorkommt; rein frz./ital. CH (Genf, Lausanne,
    Tessin) fliegt raus. So filtern wir den server-seitig rohen de|at|ch-Korpus.
    """
    de_at = ch_de = ch_other = False
    for raw in _raw_strings(work):
        s = raw.lower()
        if ("germany" in s or "deutschland" in s
                or "austria" in s or "österreich" in s):
            de_at = True
        if any(re.search(rf"\b{re.escape(c)}\b", s) for c in config.CH_GERMAN_CITIES):
            ch_de = True
        if any(re.search(rf"\b{re.escape(c)}\b", s) for c in config.CH_OTHER_CITIES):
            ch_other = True
    if de_at or ch_de:
        return True            # DE/AT oder deutschsprachige CH -> drin
    if ch_other:
        return False           # nur frz./ital. CH erkannt -> raus
    return True                # kein klares Signal -> konservativ behalten


def last_authorship(work: dict) -> dict | None:
    """Letztautor client-seitig bestimmen (author_position nicht filterbar, P6)."""
    auths = work.get("authorships", [])
    for a in auths:
        if a.get("author_position") == "last":
            return a
    return auths[-1] if auths else None


if __name__ == "__main__":
    # Smoke-Test: zählt DE-Radiotherapie-Artikel 2015-2025 via group_by.
    flt = (f"topics.id:{config.TOPIC_RADIOTHERAPY},authorships.countries:de,"
           f"type:article,publication_year:{config.YEAR_FROM}-{config.YEAR_TO}")
    g = group_by("works", flt, "publication_year")
    total = sum(x["count"] for x in g)
    print(f"Feld-Korpus (T10358, DE, 2015-2025): {total} Artikel")
