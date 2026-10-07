#!/usr/bin/env python3
"""
Beauty Helper: export the trained sentiment classifier so the web page can run it in the browser.

What this file does
-------------------
Reads results/model.joblib (word + character TF-IDF, logistic regression; see train_classifier.py) and writes a JSON file with, for each of
the two vectorizers, the vocabulary (terms in index order), the IDF weights and the logistic-regression coefficients, plus the intercept.
The page re-implements sklearn's tokenizing, TF-IDF and scoring in JavaScript (app/template.html, function classify).

It also writes a parity file (tests/parity_cases.json) with sklearn's probability for every training review and a few edge cases,
so tests/test_app_logic.js can check that the JavaScript gives the same numbers as sklearn.

Usage:  python scripts/export_model.py --model results/model.joblib --data data/reviews_labeled.csv --out app/model.json
"""
import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

EDGE_CASES = ["", "good", "Not good at all!", "light and not sticky, my skin feels hydrated", "不好用，用了脸痒", "I can't believe it's so oily   and greasy",
              "Delivery was fast but the cream made me break out", "💙 love it 💙", "ÉCRAN très bon", "a", "NOT AS DESCRIBED", "x" * 40]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=Path("results/model.joblib"))
    ap.add_argument("--data", type=Path, default=Path("data/reviews_labeled.csv"))
    ap.add_argument("--out", type=Path, default=Path("app/model.json"))
    ap.add_argument("--parity", type=Path, default=Path("tests/parity_cases.json"))
    args = ap.parse_args()

    pipe = joblib.load(args.model)
    union = pipe.named_steps["tfidf"]
    clf = pipe.named_steps["clf"]
    assert list(clf.classes_) == ["negative", "positive"], clf.classes_
    coef = clf.coef_[0]
    out, offset = {}, 0
    for name, vec in union.transformer_list:
        terms = [None] * len(vec.vocabulary_)
        for term, idx in vec.vocabulary_.items():
            terms[idx] = term
        n = len(terms)
        out[name] = {"terms": terms, "idf": [round(float(x), 10) for x in vec.idf_], "coef": [round(float(x), 10) for x in coef[offset:offset + n]],
                     "analyzer": vec.analyzer, "ngram": list(vec.ngram_range)}
        offset += n
    out["intercept"] = round(float(clf.intercept_[0]), 10)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out}: word terms {len(out['word']['terms'])}, char terms {len(out['char']['terms'])}")

    texts = pd.read_csv(args.data, dtype=str, keep_default_na=False)["review_text"].tolist() + EDGE_CASES
    proba = pipe.predict_proba(texts)[:, 1]
    args.parity.parent.mkdir(parents=True, exist_ok=True)
    args.parity.write_text(json.dumps([{"text": t, "p_positive": round(float(p), 10)} for t, p in zip(texts, proba)], ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.parity}: {len(texts)} cases")


if __name__ == "__main__":
    main()
