#!/usr/bin/env python3
"""
Beauty Helper: data check and preparation.

What this file does
-------------------
Reads the two hand-made tables (products and reviews), checks them, and prepares the files the rest of the project uses.

  products table : one row per moisturizer (name, price, skin-type label, official text, ingredients ...)
  reviews table  : one row per review, linked to a product by product_id

Checks
  ERRORS   stop the run and nothing is written (missing columns, unknown product_id, bad values, train rows without a label ...)
  WARNINGS are printed and written to the report (too few products, thin price x skin-type cells, few usable reviews ...)

Outputs (written to --out, default data/processed/), only when there are no errors
  products_with_tiers.csv   products plus price_tier (budget / mid / premium = thirds of YOUR actual prices)
  reviews_labeled_all.csv   every usable, hand-labeled TRAIN review about the product, with product name attached
  reviews_labeled.csv       the same, matched WITHIN each product: as many positives as negatives per product, the surplus
                            dropped at random (the classifier's training file; this keeps the product name from leaking the label)
  kb_labeled_test.csv       the hand-labeled KB reviews: a natural, unselected test set the classifier never trains on
  data_report.md            the numbers above in readable form, to quote in the report

How the two kinds of review differ (see docs/DATA_FORMAT.md)
  use = kb     the first ~15 reviews shown on the product page, copied unselected. Used by the assistant and for the
               "share of positive reviews" statistic. Never add hand-picked reviews here. If you hand-label them, they become
               the classifier's test set (kb_labeled_test.csv); they are NOT used for training.
  use = train  reviews picked on purpose (1-2 star AND 4-5 star, from the SAME products) to train the classifier.

aspect: only reviews about the product itself (aspect = product) are used. Reviews about delivery, packaging, the seller,
price or authenticity are aspect = service and are never used for training or for the sentiment statistics.

Usage
-----
    python scripts/check_data.py --products data/products.csv --reviews data/reviews.csv
    python scripts/check_data.py --workbook data/beauty_helper_data.xlsx        # sheets named "products" and "reviews"
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROLES = ["kb", "train_only"]    # kb = a moisturizer the assistant can recommend; train_only = any cosmetic product used only for classifier training
PRODUCT_COLS = ["product_id", "product_name", "role", "brand", "size", "platform", "url", "price_sgd", "price_date",
                "skin_type_label", "official_skin_type_text", "official_benefits_text", "main_claim",
                "description", "ingredients"]
PRODUCT_REQUIRED = ["product_id", "product_name", "platform", "role"]
PRODUCT_KB_REQUIRED = ["price_sgd", "price_date", "skin_type_label", "main_claim"]   # only needed for role = kb
PRODUCT_RECOMMENDED = ["url", "official_skin_type_text", "official_benefits_text", "description", "ingredients"]
REVIEW_COLS = ["review_id", "product_id", "platform", "review_text", "rating", "use", "aspect", "label", "usable", "skip_reason", "source"]
SKIN_TYPES = ["oily", "dry", "sensitive"]
PLATFORMS = ["Shopee", "Lazada", "Sephora SG"]
TIERS = ["budget", "mid", "premium"]
TARGET_PRODUCTS = (12, 15)      # plan: 3 price tiers x 4 to 5 products
TARGET_TRAIN_ROWS = 150          # problem statement: 150 to 200 labeled reviews
MIN_KB_PER_PRODUCT = 8           # usable knowledge-base reviews worth showing a share for


def load_table(path: Path, sheet: str) -> pd.DataFrame:
    """Read a CSV or an Excel sheet as plain text (no automatic type guessing), with whitespace trimmed."""
    if not path.exists():
        sys.exit(f"ERROR: file not found: {path}")
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet, dtype=str, keep_default_na=False)
    else:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df.loc[~(df == "").all(axis=1)].reset_index(drop=True)   # drop fully empty rows


def assign_tiers(price: pd.Series) -> pd.Series:
    """Thirds of the actual price distribution (ties broken by order), so each tier has about the same number of products."""
    rank = price.rank(method="first")
    return pd.qcut(rank, 3, labels=TIERS).astype(str)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--products", type=Path)
    ap.add_argument("--reviews", type=Path)
    ap.add_argument("--workbook", type=Path, help="one .xlsx with sheets 'products' and 'reviews'")
    ap.add_argument("--out", type=Path, default=Path("data/processed"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.workbook:
        products, reviews = load_table(args.workbook, "products"), load_table(args.workbook, "reviews")
    elif args.products and args.reviews:
        products, reviews = load_table(args.products, "products"), load_table(args.reviews, "reviews")
    else:
        ap.error("give --workbook, or both --products and --reviews")

    errors, warnings = [], []
    err, warn = errors.append, warnings.append

    # ---------- structure ----------
    for name, df, req in (("products", products, PRODUCT_REQUIRED), ("reviews", reviews, ["review_id", "product_id", "review_text", "use", "aspect", "usable"])):
        miss = [c for c in req if c not in df.columns]
        if miss:
            err(f"{name}: missing column(s) {miss}")
    for c in PRODUCT_COLS:
        if c not in products.columns:
            products[c] = ""
    for c in REVIEW_COLS:
        if c not in reviews.columns:
            reviews[c] = ""
    if errors:
        report_and_exit(errors, warnings, None)

    # ---------- products ----------
    if products["product_id"].duplicated().any():
        err(f"products: duplicate product_id(s): {sorted(products.loc[products['product_id'].duplicated(), 'product_id'].unique())}")
    for c in PRODUCT_REQUIRED:
        bad = products.loc[products[c] == "", "product_id"].tolist()
        if bad:
            err(f"products: '{c}' is empty for {bad}")
    bad_role = products.loc[(products["role"] != "") & ~products["role"].isin(ROLES), "product_id"].tolist()
    if bad_role:
        err(f"products: role must be one of {ROLES}; check {bad_role}")
    kbp = products["role"] == "kb"
    for c in PRODUCT_KB_REQUIRED:
        bad = products.loc[kbp & (products[c] == ""), "product_id"].tolist()
        if bad:
            err(f"products: '{c}' is empty for knowledge-base product(s) {bad}")
    bad_skin = products.loc[(products["skin_type_label"] != "") & ~products["skin_type_label"].isin(SKIN_TYPES), "product_id"].tolist()
    if bad_skin:
        err(f"products: skin_type_label must be one of {SKIN_TYPES}; check {bad_skin}")
    price = pd.to_numeric(products["price_sgd"].str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    bad_price = products.loc[(products["price_sgd"] != "") & (price.isna() | (price <= 0)), "product_id"].tolist()
    if bad_price:
        err(f"products: price_sgd is not a positive number for {bad_price}")
    products["price_sgd"] = price
    for c in PRODUCT_RECOMMENDED:
        bad = products.loc[kbp & (products[c] == ""), "product_id"].tolist()
        if bad:
            warn(f"products: '{c}' is empty for knowledge-base product(s) {bad}")
    other_platform = products.loc[(products["platform"] != "") & ~products["platform"].isin(PLATFORMS), "product_id"].tolist()
    if other_platform:
        warn(f"products: platform is not one of {PLATFORMS} for {other_platform}")
    n_prod = int(kbp.sum())
    n_train_only = int((products["role"] == "train_only").sum())
    if n_prod < TARGET_PRODUCTS[0]:
        warn(f"products: only {n_prod} knowledge-base products; the plan is {TARGET_PRODUCTS[0]} to {TARGET_PRODUCTS[1]} (problem statement says 15 to 30)")
    elif n_prod > 30:
        warn(f"products: {n_prod} knowledge-base products is more than the problem statement's 15 to 30")

    # ---------- reviews ----------
    if reviews["review_id"].duplicated().any():
        err("reviews: duplicate review_id values")
    unknown = sorted(set(reviews["product_id"]) - set(products["product_id"]))
    if unknown:
        err(f"reviews: product_id not found in the products table: {unknown}")
    if (reviews["review_text"] == "").any():
        err(f"reviews: empty review_text in rows {reviews.index[reviews['review_text'] == ''].map(lambda i: i + 2).tolist()} (spreadsheet row numbers)")
    for col, allowed in (("use", ["kb", "train"]), ("aspect", ["product", "service"]), ("usable", ["yes", "no"])):
        bad = reviews.loc[~reviews[col].isin(allowed), "review_id"].tolist()
        if bad:
            err(f"reviews: '{col}' must be one of {allowed}; check {bad[:10]}{' ...' if len(bad) > 10 else ''}")
    bad = reviews.loc[(reviews["label"] != "") & ~reviews["label"].isin(["positive", "negative"]), "review_id"].tolist()
    if bad:
        err(f"reviews: label must be positive or negative (or empty); check {bad[:10]}")
    rating = pd.to_numeric(reviews["rating"], errors="coerce")
    bad = reviews.loc[(reviews["rating"] != "") & (rating.isna() | (rating < 1) | (rating > 5)), "review_id"].tolist()
    if bad:
        err(f"reviews: rating must be 1 to 5 (or empty); check {bad[:10]}")
    reviews["rating"] = rating
    usable_yes = (reviews["usable"] == "yes") & (reviews["aspect"] == "product")
    bad = reviews.loc[usable_yes & (reviews["use"] == "train") & (reviews["label"] == ""), "review_id"].tolist()
    if bad:
        err(f"reviews: {len(bad)} usable 'train' review(s) have no label (e.g. {bad[:5]}); the classifier needs a hand label for every one")
    if errors:
        report_and_exit(errors, warnings, None)

    norm = reviews["review_text"].str.lower().str.replace(r"\s+", " ", regex=True)
    dup = norm.duplicated(keep="first")
    if dup.any():
        warn(f"reviews: {int(dup.sum())} duplicate review text(s); duplicates are removed from the output files")
    reviews = reviews.loc[~dup].copy()
    svc_yes = reviews.loc[(reviews["usable"] == "yes") & (reviews["aspect"] == "service"), "review_id"].tolist()
    if svc_yes:
        warn(f"reviews: {len(svc_yes)} review(s) are aspect=service but usable=yes; service reviews are ignored (e.g. {svc_yes[:5]})")
    usable_yes = (reviews["usable"] == "yes") & (reviews["aspect"] == "product")
    nobody = reviews.loc[(reviews["usable"] == "no") & (reviews["skip_reason"] == ""), "review_id"].tolist()
    if nobody:
        warn(f"reviews: {len(nobody)} review(s) marked usable=no have no skip_reason (e.g. {nobody[:5]})")
    bad = reviews.loc[usable_yes & (reviews["use"] == "kb") & (reviews["label"] == ""), "review_id"]
    if len(bad):
        warn(f"reviews: {len(bad)} usable 'kb' review(s) have no hand label; labeled kb reviews are your natural test set for the classifier")
    if reviews["source"].str.contains("synthetic", case=False).any():
        warn("reviews: SYNTHETIC rows present; do not report anything computed from them")

    # ---------- tiers and coverage ----------
    products["price_tier"] = ""
    kbprod = products[kbp]
    if n_prod >= 3:
        products.loc[kbp, "price_tier"] = assign_tiers(kbprod["price_sgd"]).values
        kbprod = products[kbp]
    tier_bounds = kbprod.groupby("price_tier")["price_sgd"].agg(["min", "max", "count"]).reindex(TIERS) if n_prod >= 3 else None
    grid = pd.crosstab(kbprod["skin_type_label"], kbprod["price_tier"]).reindex(index=SKIN_TYPES, columns=TIERS, fill_value=0) if n_prod >= 3 else None
    if grid is not None:
        thin = [f"{s}/{t}" for s in SKIN_TYPES for t in TIERS if grid.loc[s, t] == 0]
        if thin:
            warn(f"coverage: no product for skin type/price tier {thin}; evaluation questions for those cells cannot be answered")
        warn_if_confounded(kbprod, warn, None)

    kb = reviews[(reviews["use"] == "kb")]
    kb_on_train_only = sorted(set(kb["product_id"]) - set(products.loc[kbp, "product_id"]))
    if kb_on_train_only:
        warn(f"reviews: use=kb reviews belong to product(s) that are not role=kb: {kb_on_train_only}")
    kb_usable = kb[(kb["usable"] == "yes") & (kb["aspect"] == "product")].groupby("product_id").size().reindex(products.loc[kbp, "product_id"], fill_value=0)
    short = kb_usable[kb_usable < MIN_KB_PER_PRODUCT]
    if len(short):
        warn(f"knowledge base: fewer than {MIN_KB_PER_PRODUCT} usable 'kb' reviews for {short.to_dict()}")
    kb_rating = kb["rating"].dropna()

    # ---------- training file (use = train only) and natural test file (use = kb) ----------
    lab = reviews[usable_yes & reviews["label"].isin(["positive", "negative"])].merge(
        products[["product_id", "product_name"]], on="product_id", how="left")
    cols = ["review_id", "product_id", "platform", "product_name", "review_text", "label", "use", "source"]
    lab_all = lab[lab["use"] == "train"][cols].copy()
    kb_test = lab[lab["use"] == "kb"][cols].copy()
    counts = lab_all["label"].value_counts().to_dict()
    n_pos, n_neg = counts.get("positive", 0), counts.get("negative", 0)
    # Match positives and negatives inside each product. If one product gave 11 positives and 1 negative, the model would learn
    # "this product's name means positive"; keeping 1 + 1 removes that shortcut, and the total stays 1:1.
    parts, dropped, one_label = [], [], []
    for pid, g in lab_all.groupby("product_id"):
        pos_g, neg_g = g[g["label"] == "positive"], g[g["label"] == "negative"]
        m = min(len(pos_g), len(neg_g))
        if m == 0:
            one_label.append(f"{pid} (pos {len(pos_g)}, neg {len(neg_g)})")
            continue
        parts += [pos_g.sample(n=m, random_state=args.seed), neg_g.sample(n=m, random_state=args.seed)]
        if max(len(pos_g), len(neg_g)) > m:
            dropped.append(f"{pid}: {len(pos_g)} pos / {len(neg_g)} neg -> keeps {m} + {m}")
    balanced = pd.concat(parts).sort_values("review_id") if parts else lab_all.iloc[0:0]
    minority = len(balanced) // 2
    if one_label:
        warn("training: products with only one label are left out of the training file (they would only teach the product name): "
             + ", ".join(one_label))
    if dropped:
        warn("training: matching positives to negatives within each product drops surplus reviews: " + "; ".join(dropped[:12])
             + (" ..." if len(dropped) > 12 else "") + ". More product-negative reviews from those products would let you keep more.")
    if len(balanced) < TARGET_TRAIN_ROWS:
        need = (TARGET_TRAIN_ROWS - len(balanced) + 1) // 2
        warn(f"training: {len(balanced)} rows ({minority} positive + {minority} negative) after per-product matching; the problem statement "
             f"plans {TARGET_TRAIN_ROWS} to 200 rows, so about {need} more matched pairs are needed")
    n_train_products = balanced["product_id"].nunique() if len(balanced) else 0
    if 0 < n_train_products < 6:
        warn(f"training: reviews come from only {n_train_products} product(s); use at least 6 so the by-product check means something")
    n_kb_neg = int((kb_test["label"] == "negative").sum())
    if len(kb_test) and n_kb_neg < 5:
        warn(f"test set: only {n_kb_neg} negative review(s) among {len(kb_test)} labeled kb reviews; the test says little about negatives")
    aspect_counts = reviews["aspect"].value_counts().to_dict()

    # ---------- report ----------
    lines = ["# Data report", "", f"Knowledge-base products: **{n_prod}** (plus {n_train_only} training-only)  |  reviews in table (after removing duplicates): **{len(reviews)}**", ""]
    if grid is not None:
        lines += ["## Products by skin type and price tier (tiers are thirds of your own prices)", "",
                  "| skin type | " + " | ".join(TIERS) + " |", "| --- | --- | --- | --- |"]
        lines += [f"| {s} | " + " | ".join(str(int(grid.loc[s, t])) for t in TIERS) + " |" for s in SKIN_TYPES] + [""]
        lines += ["| tier | min SGD | max SGD | products |", "| --- | --- | --- | --- |"]
        for t in TIERS:
            r = tier_bounds.loc[t]
            lines.append(f"| {t} | {r['min']:.2f} | {r['max']:.2f} | {int(r['count'])} |")
        lines.append("")
    lines += ["## Knowledge-base reviews (use = kb)", "",
              f"- usable per product: min {int(kb_usable.min()) if len(kb_usable) else 0}, median {kb_usable.median() if len(kb_usable) else 0:g}, max {int(kb_usable.max()) if len(kb_usable) else 0}",
              f"- kb reviews with a rating: {len(kb_rating)}; share rated 1 to 3 stars: {((kb_rating <= 3).mean() * 100):.0f}%" if len(kb_rating) else "- no ratings recorded for kb reviews",
              f"- hand-labeled kb reviews (natural test set): {len(kb_test)}, of which negative: {n_kb_neg}",
              f"- reviews by aspect (all rows): {aspect_counts}", ""]
    lines += ["## Classifier training data (use = train, aspect = product, hand-labeled)", "",
              f"- all labeled: {len(lab_all)} (positive {n_pos}, negative {n_neg})",
              f"- matched file (positives = negatives within each product): {len(balanced)} rows from {n_train_products} products",
              f"- plan: {TARGET_TRAIN_ROWS} to 200", ""]
    lines += ["## Warnings", ""] + ([f"- {w}" for w in warnings] or ["- none"]) + [""]
    text = "\n".join(lines)

    args.out.mkdir(parents=True, exist_ok=True)
    products.to_csv(args.out / "products_with_tiers.csv", index=False, encoding="utf-8")
    lab_all.to_csv(args.out / "reviews_labeled_all.csv", index=False, encoding="utf-8")
    kb_test.to_csv(args.out / "kb_labeled_test.csv", index=False, encoding="utf-8")
    balanced.to_csv(args.out / "reviews_labeled.csv", index=False, encoding="utf-8")
    (args.out / "data_report.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"Wrote 5 files to {args.out}/. Train and test the classifier with:\n"
          f"  python scripts/train_classifier.py --data {args.out / 'reviews_labeled.csv'} "
          f"--external-test {args.out / 'kb_labeled_test.csv'} --out results/")


def warn_if_confounded(products: pd.DataFrame, warn, medians: dict) -> None:
    """Warn if one skin type is concentrated in one price tier, since then price and skin type cannot be told apart."""
    for s in SKIN_TYPES:
        sub = products[products["skin_type_label"] == s]
        if len(sub) >= 3 and sub["price_tier"].nunique() == 1:
            warn(f"coverage: every '{s}' product is in the '{sub['price_tier'].iloc[0]}' tier, so price and skin type are confounded")


def report_and_exit(errors: list, warnings: list, _unused) -> None:
    print("ERRORS (nothing was written):")
    for e in errors:
        print(f"  - {e}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    sys.exit(1)


if __name__ == "__main__":
    main()
