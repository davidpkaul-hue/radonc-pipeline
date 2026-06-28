# RadOnc Reverse-Engineering — core pipeline

A reproducible pipeline that reconstructs a medical specialty from OpenAlex by
reading **locations and seniority from the raw affiliation strings** rather than from
the disambiguated institution tags. This repository accompanies the methods paper:

> Kaul D. *Reverse-engineering a medical specialty from OpenAlex: a reproducible
> pipeline for affiliation disambiguation and author localisation in radiation
> oncology.* Preprint, 2026. doi:[Preprint DOI]

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
| `scripts/validation_sample.py` | Draws the random gold-standard sample for the localisation accuracy check |
| `scripts/validation_eval.py` | Computes precision/recall/F1 (strict vs. gated vs. naïve) against the gold standard |
| `validation/validation_gold_n100.csv` | The manually coded gold standard (100 last authors) behind Table 1 of the paper |
| `validation/validation_results.csv` | The resulting precision/recall/F1 table |

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

## Reproducing the validation (Table 1)

The localisation accuracy reported in the paper is reproducible from the included gold
standard:

```bash
mkdir -p outputs/validation
cp validation/validation_gold_n100.csv outputs/validation/validation_sample.csv
cd scripts
python validation_eval.py 100      # micro-averaged precision/recall/F1 for the 100 coded papers
```

To regenerate a fresh sample for independent coding, run `python validation_sample.py`
(needs the corpus in `cache/`), then code the `gold_cities` column by hand.

## Data & licence

This repository is archived on Zenodo (current version **v1.1**; the v1.0 record is
doi:10.5281/zenodo.20994799, and the v1.1 release receives its own version DOI).
Underlying records are from OpenAlex (https://openalex.org, CC0). Code is released
under the MIT License (see `LICENSE`). The frozen corpus snapshot and the provenance
manifest are archived separately on Zenodo (see the paper).

## Author

David Kaul — Professur für Strahlentherapie, HMU Health and Medical University,
Potsdam, Germany. ORCID: 0000-0002-7906-5629.
