#!/usr/bin/env python3
"""
Beauty Helper: quick audit of a pile of hand-labeled reviews, before they go into the tables.

What this file does
-------------------
Reads reviews and labels from either
  --py   a Python file that defines lists named DATA_PART1, DATA_PART2 ... of (text, label) tuples, or
  --csv  a CSV with columns review_text,label
and reports, per label:
  * counts, and exact duplicates (ignoring case and spacing)
  * very short reviews (3 words or fewer), whose label cannot be checked from the text
  * heuristic FLAGS that point at reviews a human should look at again:
      not_tried     the reviewer says they have not tried it yet, or only hopes it works
      service_only  talks about delivery, packaging, seller or price, and says nothing about skin or the product itself
      authenticity  fake, seal, manufacturing date, "not as described" and similar
      non_english   contains common Tagalog or Malay words (the plan asks for Singapore reviews)
      region_signal mentions baht, peso, ringgit and similar (a sign the review is from another country)
and compares review length by label, because a model can learn "short means negative" instead of sentiment.

The flags are keyword rules, not judgements. They tell you where to look; YOU decide whether a review is usable
and what its label is. Writes audit_flags.csv (one row per review, to filter in a spreadsheet).

Usage
-----
    python scripts/audit_reviews.py --py data_parts.py --out audit_flags.csv
    python scripts/audit_reviews.py --csv reviews.csv
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

SERVICE = re.compile(r"deliver|packag|packed|packing|bubble|seller|shipping|shipped|courier|parcel|\bbox\b|\bdent(ed|s)?\b|envelope|refund|"
                     r"customer service|arrived|received|flash sale|voucher|discount|\bsale\b|free gift|freebie|wrong item|incorrect|"
                     r"incomplete|price|cheaper|\bstore\b|\bshop\b", re.I)
PRODUCT = re.compile(r"\bskin|\bface|moistur|hydrat|acne|pimple|break ?out|broke me out|outbreak|\brash|\bitch|\bburn|\bsting|irritat|redness|"
                     r"\bdry|dryness|oily|sticky|greasy|texture|smell|absorb|effect|result|improve|smooth|glow|dark spot|pigment|"
                     r"comedone|pilling|eczema|\bspots?\b|sensitive|\bworks?\b|\bworked\b|dullness|pimples", re.I)
NOT_TRIED = re.compile(r"haven'?t (tried|used)|not (yet )?(tried|used)|yet to (try|use)|hope(fully)? (it|this|to)|hope (it|this)|"
                       r"wanna try|want to try|will try|can'?t wait to (use|try)|first time (using|trying)|trying this for the first|"
                       r"hope to see|looking forward to using|just (bought|tried)|not sure\.?$", re.I)
AUTH = re.compile(r"fake|authentic|genuine|counterfeit|legit|\bseal|manufactur|expiry|\bbatch|not as described|scam|suspicious|original", re.I)
REGION = re.compile(r"baht|\bphp\b|peso|ringgit|\brm ?\d|\bmyr\b", re.I)
LOCAL_WORDS = {"ako", "yung", "yun", "tapi", "tkde", "takde", "tpi", "nasib", "pakai", "jerawat", "dorang", "sbb", "jer", "utk",
               "imbis", "sakin", "sayang", "bakit", "kaya", "butas", "ubos", "bago", "nag", "mag", "ng", "kemik2", "hbs", "baik",
               "ko", "ginagamit", "palala", "mahal", "kati", "langsung", "kat", "nak", "tak", "huru", "hara"}


def load(args) -> pd.DataFrame:
    if args.py:
        spec = importlib.util.spec_from_file_location("data_parts", args.py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = []
        parts = sorted((n for n in dir(mod) if n.upper().startswith("DATA_PART")), key=lambda n: int(re.sub(r"\D", "", n) or 0))
        if not parts:
            sys.exit("ERROR: no DATA_PART... lists found in the file")
        for name in parts:
            for i, (text, label) in enumerate(getattr(mod, name), 1):
                rows.append({"part": name, "row": i, "review_text": str(text).strip(), "label": str(label).strip().lower()})
        return pd.DataFrame(rows)
    df = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
    if not {"review_text", "label"} <= set(df.columns):
        sys.exit("ERROR: CSV needs columns review_text and label")
    df = df[["review_text", "label"]].copy()
    df.insert(0, "row", range(1, len(df) + 1))
    df.insert(0, "part", "csv")
    return df


def flags_for(text: str) -> list:
    words = re.findall(r"[A-Za-z0-9'’]+", text)
    out = []
    if len(words) <= 3:
        out.append("too_short")
    if NOT_TRIED.search(text):
        out.append("not_tried")
    if SERVICE.search(text) and not PRODUCT.search(text):
        out.append("service_only")
    if AUTH.search(text):
        out.append("authenticity")
    if {w.lower() for w in words} & LOCAL_WORDS or re.search(r"[^\x00-\x7F]", text):
        out.append("non_english")
    if REGION.search(text):
        out.append("region_signal")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--py", type=Path)
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--out", type=Path, default=Path("audit_flags.csv"))
    args = ap.parse_args()
    if not args.py and not args.csv:
        ap.error("give --py or --csv")
    df = load(args)

    bad = sorted(set(df["label"]) - {"positive", "negative"})
    if bad:
        sys.exit(f"ERROR: unexpected label(s) {bad}")
    df["words"] = df["review_text"].str.findall(r"[A-Za-z0-9'’]+").str.len()
    df["norm"] = df["review_text"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    df["duplicate_of_earlier"] = df["norm"].duplicated(keep="first")
    df["flags"] = df["review_text"].map(flags_for)
    df["flag_text"] = df["flags"].map(", ".join)

    print(f"Reviews: {len(df)}   positive {int((df.label == 'positive').sum())}   negative {int((df.label == 'negative').sum())}")
    uniq = df[~df.duplicate_of_earlier]
    print(f"After removing exact duplicates: {len(uniq)}   positive {int((uniq.label == 'positive').sum())}   "
          f"negative {int((uniq.label == 'negative').sum())}   ({int(df.duplicate_of_earlier.sum())} duplicates)")
    top = df.loc[df["duplicate_of_earlier"], "norm"].value_counts().head(5)
    if len(top):
        print("Most repeated texts (extra copies):", "; ".join(f"'{t[:40]}' x{n}" for t, n in top.items()))

    print("\nFlags by label (a review can have several; unique reviews only):")
    names = ["too_short", "not_tried", "service_only", "authenticity", "non_english", "region_signal"]
    table = pd.DataFrame({n: [int(uniq.loc[uniq["label"] == l, "flags"].map(lambda f: n in f).sum()) for l in ("positive", "negative")] for n in names},
                         index=["positive", "negative"]).T
    table["positive %"] = (table["positive"] / max(1, (uniq["label"] == "positive").sum()) * 100).round(0).astype(int)
    table["negative %"] = (table["negative"] / max(1, (uniq["label"] == "negative").sum()) * 100).round(0).astype(int)
    print(table.to_string())

    print("\nWords per review (unique reviews):")
    print(uniq.groupby("label")["words"].describe()[["count", "mean", "50%", "max"]].round(1).to_string())

    flagged = df[df.flag_text != ""]
    df.drop(columns=["norm", "flags"]).to_csv(args.out, index=False, encoding="utf-8")
    print(f"\n{len(flagged)} of {len(df)} reviews have at least one flag. Wrote {args.out}: filter the 'flag_text' column and decide, "
          f"review by review, whether it is usable and whether the label is right.")


if __name__ == "__main__":
    main()
