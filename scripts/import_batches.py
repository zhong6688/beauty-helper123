#!/usr/bin/env python3
"""
Beauty Helper: turn hand-collected review lists into draft rows for the reviews table.

What this file does
-------------------
You collect reviews as Python lists of (text, label) tuples, one list per product and label, for example

    TORRIDEN_POSITIVE = [("Lightweight, not sticky ...", 'positive'), ...]
    TORRIDEN_NEGATIVE = [("Doesn't absorb well ...", 'negative'), ...]

This script reads those lists and writes a CSV in the layout of the reviews table (docs/DATA_FORMAT.md), with SUGGESTIONS filled in:
  aspect       service if the review only talks about delivery, packaging, seller, price or authenticity, else product
  usable       no for suggested service reviews, "not tried yet", very short, non-English or other-country reviews, and duplicates
  skip_reason  why the suggestion says no
  auto_flags   the keyword flags behind the suggestion (same rules as audit_reviews.py)
The suggestions are keyword rules. Open the CSV in Excel, read every row marked usable=no or with flags, correct what is wrong,
and then paste the rows into the reviews sheet. The label is whatever YOU wrote in the list; this script never changes it.

Which list belongs to which product
-----------------------------------
Pass --map "LISTNAME=PRODUCT_ID:USE,..." where USE is train or kb, for example

    python scripts/import_batches.py --py batches.py \\
        --map "TORRIDEN_POSITIVE=P01:train,TORRIDEN_NEGATIVE=P01:train" --out reviews_draft.csv

Lists named like P01_TRAIN_POS or P03_KB need no --map entry: product id and use are read from the name.
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_reviews import flags_for  # noqa: E402  (same keyword rules as the audit)

COLUMNS = ["review_id", "product_id", "platform", "review_text", "rating", "use", "aspect", "label", "usable", "skip_reason", "source", "auto_flags"]
NAME_RE = re.compile(r"^(P\d+)_(TRAIN|KB)(?:_.*)?$", re.I)


def parse_map(text: str) -> dict:
    out = {}
    for item in filter(None, (t.strip() for t in text.split(","))):
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(P\d+):(train|kb)", item, re.I)
        if not m:
            sys.exit(f"ERROR: bad --map entry '{item}'. Use LISTNAME=PRODUCT_ID:USE, for example TORRIDEN_POSITIVE=P01:train")
        out[m.group(1)] = (m.group(2).upper(), m.group(3).lower())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--py", type=Path, required=True, help="Python file with the lists")
    ap.add_argument("--map", type=str, default="", help="LISTNAME=PRODUCT_ID:USE,... (use train or kb)")
    ap.add_argument("--platform", type=str, default="Shopee", help="platform to write on every row (edit later if mixed)")
    ap.add_argument("--date", type=str, default="", help="collection date for the source column, e.g. 2026-10-12")
    ap.add_argument("--start-id", type=int, default=1, help="number of the first review_id (R0001 = 1)")
    ap.add_argument("--out", type=Path, default=Path("reviews_draft.csv"))
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location("batches", args.py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mapping = parse_map(args.map)

    rows, skipped_names = [], []
    for name in [n for n in dir(mod) if not n.startswith("_") and isinstance(getattr(mod, n), list)]:
        items = getattr(mod, name)
        if not items or not all(isinstance(i, tuple) and len(i) == 2 for i in items):
            continue
        if name in mapping:
            pid, use = mapping[name]
        elif NAME_RE.match(name):
            m = NAME_RE.match(name)
            pid, use = m.group(1).upper(), m.group(2).lower()
        else:
            skipped_names.append(name)
            continue
        for text, label in items:
            rows.append({"list": name, "product_id": pid, "use": use, "review_text": str(text).strip(), "label": str(label).strip().lower()})
    if skipped_names:
        print(f"NOTE: no product/use known for list(s) {skipped_names}; add them to --map (LISTNAME=PRODUCT_ID:USE) or rename them like P01_TRAIN_POS")
    if not rows:
        sys.exit("ERROR: no lists were imported")

    df = pd.DataFrame(rows)
    bad = sorted(set(df["label"]) - {"positive", "negative"})
    if bad:
        sys.exit(f"ERROR: unexpected label(s) {bad}; only positive and negative are allowed")
    df["norm"] = df["review_text"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    df["is_dup"] = df["norm"].duplicated(keep="first")
    df["flags"] = df["review_text"].map(flags_for)

    def decide(r):
        f = set(r["flags"])
        reasons = []
        aspect = "service" if "service_only" in f else "product"
        if aspect == "service":
            reasons.append("service only (delivery, packaging, seller, price or authenticity)")
        if "not_tried" in f:
            reasons.append("maybe not tried yet (check)")
        if "too_short" in f:
            reasons.append("too short to judge")
        if "non_english" in f:
            reasons.append("non-English or mixed (plan says Singapore English/Singlish)")
        if "region_signal" in f:
            reasons.append("other-country signal (baht, peso, ringgit)")
        if r["is_dup"]:
            reasons.append("duplicate")
        # not_tried alone is only a prompt to look again: it does not switch usable off by itself
        hard = aspect == "service" or r["is_dup"] or bool(f & {"too_short", "non_english", "region_signal"})
        return pd.Series({"aspect": aspect, "usable": "no" if hard else "yes", "skip_reason": "; ".join(reasons)})

    df = pd.concat([df, df.apply(decide, axis=1)], axis=1)
    df["review_id"] = [f"R{args.start_id + i:04d}" for i in range(len(df))]
    df["platform"] = args.platform
    df["rating"] = ""
    df["source"] = ("manual-copy " + args.date).strip()
    df["auto_flags"] = df["flags"].map(", ".join)
    out = df[COLUMNS]
    out.to_csv(args.out, index=False, encoding="utf-8")

    print(f"Wrote {len(out)} draft rows to {args.out}\n")
    print("Suggestions by list (product aspect and usable) - YOU decide, this is only a first pass:")
    summary = df.groupby(["list", "product_id", "use", "label"]).agg(
        rows=("review_text", "size"),
        product_aspect=("aspect", lambda s: int((s == "product").sum())),
        usable_yes=("usable", lambda s: int((s == "yes").sum())))
    print(summary.to_string())
    check = df[df["auto_flags"] != ""]
    print(f"\n{len(check)} of {len(df)} rows have flags; {int((df['usable'] == 'no').sum())} are suggested usable=no. "
          f"Open {args.out} and read every row with a skip_reason or flag.")


if __name__ == "__main__":
    main()
