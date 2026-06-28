"""Validierungs-Auswertung — Precision/Recall/F1 gegen den manuellen Goldstandard.

Liest die ausgefüllte `validation_sample.csv` (Spalte `gold_cities` kodiert) und
berechnet für jedes Verfahren (strict / gated / naive) mikro-gemittelte
Precision, Recall und F1 auf Ebene der (Paper, Stadt)-Zuordnungen.

Definitionen je Paper:
  TP = vom Verfahren genannte Stadt, die auch im Gold steht
  FP = vom Verfahren genannte Stadt, die NICHT im Gold steht
  FN = Gold-Stadt, die das Verfahren NICHT nennt
`gold = none` bedeutet leere Gold-Menge (jede genannte Stadt ist dann ein FP).

Schreibt:  outputs/validation/validation_results.csv  + Konsolenbericht

Aufruf:
  python validation_eval.py            # nur explizit gefüllte Zeilen
  python validation_eval.py 100        # erste 100 Zeilen als 'reviewed' werten;
                                       # leere gold-Zellen darin zählen als 'none'
"""
from __future__ import annotations

import csv
import sys

import config

VALID = config.OUTPUTS / "validation"
METHODS = ["strict_cities", "gated_cities", "naive_cities"]


def parse(cell: str) -> set[str]:
    cell = (cell or "").strip()
    if not cell or cell.lower() in {"none", "keine", "-"}:
        return set()
    return {c.strip() for c in cell.split(";") if c.strip()}


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main(reviewed: int | None = None) -> None:
    src = VALID / "validation_sample.csv"
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    if reviewed:
        # Erste `reviewed` Zeilen gelten als geprüft; leere gold-Zelle = 'none'.
        coded = rows[:reviewed]
        mode = f"erste {reviewed} Zeilen (leer = none)"
    else:
        coded = [r for r in rows if (r.get("gold_cities") or "").strip()]
        mode = "nur explizit gefüllte Zeilen"
    if not coded:
        print(f"[eval] Keine kodierten Zeilen in {src} — bitte 'gold_cities' ausfüllen.")
        return

    agg = {m: {"tp": 0, "fp": 0, "fn": 0} for m in METHODS}
    none_gold = sum(1 for r in coded if not parse(r["gold_cities"]))
    for r in coded:
        gold = parse(r["gold_cities"])
        for m in METHODS:
            pred = parse(r[m])
            agg[m]["tp"] += len(pred & gold)
            agg[m]["fp"] += len(pred - gold)
            agg[m]["fn"] += len(gold - pred)

    out = VALID / "validation_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["method", "TP", "FP", "FN", "precision", "recall", "F1"])
        print(f"\n[eval] {len(coded)} Paper — {mode} "
              f"({none_gold} davon ohne Gold-Stadt)\n")
        print(f"{'Verfahren':<10} {'P':>6} {'R':>6} {'F1':>6}   (TP/FP/FN)")
        for m in METHODS:
            a = agg[m]
            p, r, fsc = prf(a["tp"], a["fp"], a["fn"])
            wr.writerow([m.replace("_cities", ""), a["tp"], a["fp"], a["fn"],
                         f"{p:.3f}", f"{r:.3f}", f"{fsc:.3f}"])
            print(f"{m.replace('_cities',''):<10} {p:>6.3f} {r:>6.3f} {fsc:>6.3f}"
                  f"   ({a['tp']}/{a['fp']}/{a['fn']})")
    print(f"\n[eval] Tabelle -> {out}")


if __name__ == "__main__":
    rev = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(rev)
