#!/usr/bin/env python3
"""
Beauty Helper: build the knowledge base and the single-file web page (app/index.html).

What this file does
-------------------
1. Reads the product table (data/products.csv; only role = kb products) and the reviews about each product:
     - data/reviews.csv                 reviews copied from product pages (use = kb), for products whose reviews are in this table
     - data/reviews_labeled.csv         the hand-labeled classifier data, for products whose reviews were collected in batches
     - data/pending_new_rows.csv        extra labeled reviews not yet in the classifier data
   Only reviews about the product itself (aspect = product, usable = yes) are kept; duplicates are removed.
2. Gives every review a sentiment tag: the author's hand label where there is one, otherwise the classifier's prediction
   (results/model.joblib). The source is stored with the tag ("hand" or "model") and shown on the page.
3. Writes app/kb.json and inserts the knowledge base, the exported model (app/model.json), app/logic.js and the app's evaluation
   questions (evals/app_eval_questions.json) into app/template.html, producing the self-contained app/index.html.

Usage:  python scripts/build_app.py
"""
import json
import re
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
# reviews of these products live in the classifier data, under these names
BATCH_NAME_TO_ID = {"Torriden": "P01", "CeraVe cream": "P05"}
PRODUCT_FIELDS = ["product_id", "product_name", "brand", "size", "platform", "url", "price_sgd", "price_date", "skin_type_label",
                  "skin_types_on_page", "official_skin_type_text", "official_benefits_text", "main_claim", "description", "ingredients"]


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def main() -> None:
    products = pd.read_csv(ROOT / "data/products.csv", dtype=str, keep_default_na=False)
    products = products[products["role"] == "kb"].copy()
    products["price_sgd"] = products["price_sgd"].astype(float)
    kb_ids = list(products["product_id"])

    rows = []   # (product_id, text, hand_label or "", origin)
    rev = pd.read_csv(ROOT / "data/reviews.csv", dtype=str, keep_default_na=False)
    rev = rev[(rev["usable"] == "yes") & (rev["aspect"] == "product") & rev["product_id"].isin(kb_ids)]
    for _, r in rev.iterrows():
        rows.append((r["product_id"], r["review_text"], "", "copied from the product page in page order"))
    batch = pd.read_csv(ROOT / "data/reviews_labeled.csv", dtype=str, keep_default_na=False)
    for _, r in batch.iterrows():
        pid = BATCH_NAME_TO_ID.get(r["product_name"])
        if pid in kb_ids:
            rows.append((pid, r["review_text"], r["label"], "collected in a batch, selected by star filter"))
    pend_path = ROOT / "data/pending_new_rows.csv"
    if pend_path.exists():
        for _, r in pd.read_csv(pend_path, dtype=str, keep_default_na=False).iterrows():
            pid = BATCH_NAME_TO_ID.get(r["product_name"])
            if pid in kb_ids:
                rows.append((pid, r["review_text"], r["label"], "collected in a batch, selected by star filter"))

    seen, kept = set(), []
    for pid, text, label, origin in rows:
        key = (pid, norm(text))
        if key in seen:
            continue
        seen.add(key)
        kept.append((pid, text, label, origin))

    model = joblib.load(ROOT / "results/model.joblib")
    reviews, counters = [], {}
    for pid, text, label, origin in kept:
        counters[pid] = counters.get(pid, 0) + 1
        if label in ("positive", "negative"):
            sentiment, source = label, "hand"
        else:
            sentiment, source = ("positive" if model.predict_proba([text])[0][1] >= 0.5 else "negative"), "model"
        reviews.append({"id": f"{pid}-{counters[pid]:03d}", "product_id": pid, "text": text, "sentiment": sentiment,
                        "sentiment_source": source, "origin": origin})

    kb = {"built": pd.Timestamp.now().strftime("%Y-%m-%d"),
          "products": products[PRODUCT_FIELDS].to_dict(orient="records"), "reviews": reviews}
    (ROOT / "app/kb.json").write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = pd.DataFrame(reviews).groupby(["product_id", "sentiment"]).size().unstack(fill_value=0)
    print("knowledge base:", len(kb["products"]), "products,", len(reviews), "reviews")
    print(summary.to_string())

    template = ROOT / "app/template.html"
    if template.exists():
        eval_path = ROOT / "evals/app_eval_questions.json"
        html = template.read_text(encoding="utf-8")
        parts = {"__KB__": json.dumps(kb, ensure_ascii=False), "__MODEL__": (ROOT / "app/model.json").read_text(encoding="utf-8"),
                 "__LOGIC__": (ROOT / "app/logic.js").read_text(encoding="utf-8"),
                 "__EVALS__": eval_path.read_text(encoding="utf-8") if eval_path.exists() else "[]"}
        for key, value in parts.items():
            assert html.count(key) == 1, key
            html = html.replace(key, value.replace("</script", "<\\/script"))
        (ROOT / "app/index.html").write_text(html, encoding="utf-8")
        print("wrote app/index.html,", round(len(html) / 1024), "KB")


if __name__ == "__main__":
    main()
