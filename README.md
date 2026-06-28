# RadOnc Reverse-Engineering — core pipeline

A reproducible pipeline that reconstructs a medical specialty from OpenAlex by
reading **locations and seniority from the raw affiliation strings** rather than from
the disambiguated institution tags. This repository accompanies the methods paper:

> Kaul D, Wernecke K-D, Budach V. *Reverse-engineering a medical specialty from
> OpenAlex: a reproducible pipeline for affiliation disambiguation and author
> localisation in radiation oncology.* Preprint, 2026. doi:[Zenodo DOI]

> **Scope.** This repository contains only the **core methods pipeline** described in
> the paper (retrieval, union-corpus construction, the disambiguation/localisation
> layer, and the deposit snapshot). The downstream analysis modules (hegemony,
> collaboration, networks, gender, etc.), which belong to separate companion articles,
> are **not** included here.

## What it does

1. **Robust retrieval** — a checkpointed OpenAlex client (cursor pagination, polite
   pool, exponential backoff, resumable streaming append).
2. **Union corpus** — combines a radiotherapy topic with eight core journals via two
   separate streams (because OpenAlex AND-combines filter categories), merged and
   de-duplicated by work id; the non-German-speaking Swiss share is removed.
3. **Localisation & seniority** — a stem-based department filter, a corpus-grounded
   city gazetteer with word-boundary matching, a single-string consortium-clause
   ("DKTK") guard, three transparent location measures (strict / gated / presence),
   and a person-gated senior fallback.
4. **Provenance** — a machine-readable manifest of the exact queries and per-stage
   counts.
5. **Deposit snapshot** — a slim, frozen corpus snapshot for archiving.

See the paper for the full method and the P1–P7 data-quality catalogue.

## Files

| File | Role |
|---|---|
| `scripts/config.py` | Paths, OpenAlex config, core journals, city gazetteer, region helpers |
| `scripts/radonc_common.py` | Robust paged OpenAlex client; department/exclusion stems; helpers |
| `scripts/radonc_mining.py` | Dual-stream retrieval, merge, de-duplication, language filter |
| `scripts/radonc_geo.py` | Localisation layer: gazetteer matching, DKTK guard, three measures, senior set, coverage audit |
| `scripts/provenance.py` | Writes the machine-readable provenance manifest |
| `scripts/export_snapshot.py` | Builds the slim, deposit-ready corpus snapshot |

## Requirements

- Python 3.10+
- `requests` (see `requirements.txt`); the standard library otherwise.

```bash
pip install -r requirements.txt
```

## Usage

Set a contact e-mail for the OpenAlex polite pool in `scripts/config.py`, then:

```bash
cd scripts
python radonc_mining.py      # build the union corpus -> cache/refs.jsonl
python provenance.py         # write the provenance manifest
python radonc_geo.py         # build the senior set + run the coverage audit
python export_snapshot.py    # build the deposit snapshot
```

Caches and outputs are written under `cache/` and `outputs/` and are git-ignored.

## Data & licence

Underlying records are from OpenAlex (https://openalex.org, CC0). Code is released
under the MIT License (see `LICENSE`). The frozen corpus snapshot and the provenance
manifest are archived separately on Zenodo (see the paper).

## Author

David Kaul — Professur für Strahlentherapie, HMU Health and Medical University,
Potsdam, Germany. ORCID: 0000-0002-7906-5629.
