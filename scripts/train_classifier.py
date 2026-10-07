#!/usr/bin/env python3
"""
Beauty Helper, Part 1: review sentiment classifier (narrow ML, scikit-learn).

What this file does
-------------------
1. Loads a labeled review CSV (columns: review_id, platform, product_name, review_text, label, source).
2. Validates it (labels, duplicates, class balance, size) and prints warnings instead of failing silently.
3. Trains and compares three models with the same stratified split, the same 5-fold cross-validation, and (when the
   CSV has product names for at least 4 products) a cross-validation grouped by product, where every test fold contains
   only products the model has never seen. That last number is the honest one for "what happens on a new product":
     a. majority-class baseline        (what you get by guessing)
     b. word TF-IDF + logistic regression
     c. word + character TF-IDF + logistic regression
        (character n-grams help with Singlish spellings, typos and mixed English/Chinese text)
4. Optionally (--external-test) trains each model on ALL training rows and scores it on a separate hand-labeled file, for
   example the knowledge-base reviews you labeled (kb_labeled_test.csv). Those reviews are unselected, so they show how the
   classifier does on the reviews it will really meet; rows that also appear in the training file are removed first.
5. Writes everything needed for the report and for error analysis to --out:
     metrics.json, misclassified.csv, top_features.txt, model.joblib (final model fit on all rows)
5. Can score new text with a saved model:  --predict "text of a review"

Usage
-----
    python scripts/train_classifier.py --data data/reviews_labeled.csv --out results/
    python scripts/train_classifier.py --data data/processed/reviews_labeled.csv \\
        --external-test data/processed/kb_labeled_test.csv --out results/
    python scripts/train_classifier.py --predict "light and not sticky" --model results/model.joblib

IMPORTANT: with 150 to 200 rows the hold-out set has only 30 to 40 reviews, so one review is 2.5 to 3.3
percentage points. Report the cross-validation numbers next to the hold-out numbers, and read the
misclassified reviews by hand; do not rely on a single accuracy figure.
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, StratifiedKFold, cross_val_predict, cross_validate, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

LABELS = ["negative", "positive"]
REQUIRED_COLUMNS = ["review_text", "label"]


def load_and_validate(path: Path) -> pd.DataFrame:
    """Read the CSV and check it. Raises SystemExit on problems that make training meaningless."""
    df = pd.read_csv(path, encoding="utf-8")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: missing column(s) {missing} in {path}")
    if "review_id" not in df.columns:
        df.insert(0, "review_id", [f"R{i + 1:04d}" for i in range(len(df))])

    df["review_text"] = df["review_text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    before = len(df)
    df = df[(df["review_text"] != "") & (df["review_text"].str.lower() != "nan")]
    if len(df) < before:
        print(f"WARNING: dropped {before - len(df)} row(s) with empty text")

    bad = sorted(set(df["label"]) - set(LABELS))
    if bad:
        sys.exit(f"ERROR: unexpected label(s) {bad}; allowed labels are {LABELS}")

    dup = df.duplicated(subset="review_text", keep="first").sum()
    if dup:
        print(f"WARNING: {dup} duplicate review text(s); duplicates can leak between train and test. Removing them.")
        df = df.drop_duplicates(subset="review_text", keep="first")

    counts = df["label"].value_counts().to_dict()
    print(f"Rows: {len(df)}; class counts: {counts}")
    if len(counts) < 2:
        sys.exit("ERROR: need both positive and negative reviews")
    if min(counts.values()) < 10:
        sys.exit("ERROR: fewer than 10 reviews in a class; cross-validation is not meaningful")
    ratio = max(counts.values()) / min(counts.values())
    if ratio > 1.2:
        print(f"WARNING: classes are not balanced (ratio {ratio:.2f}); your plan says 1:1")
    if len(df) < 150:
        print(f"WARNING: only {len(df)} rows; your plan says 150 to 200. Results are less reliable.")
    if "source" in df.columns and df["source"].astype(str).str.contains("synthetic", case=False).any():
        print("WARNING: this file contains SYNTHETIC rows. Any metrics below are for testing the code only, "
              "not results you can report.")
    return df.reset_index(drop=True)


def make_models(seed: int) -> dict:
    """The three models compared in the report. Same classifier, different features, plus a dumb baseline."""
    word = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    char = TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)
    lr = lambda: LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced", random_state=seed)
    return {
        "baseline_majority": Pipeline([("clf", DummyClassifier(strategy="most_frequent"))]),
        "word_tfidf_lr": Pipeline([("tfidf", word), ("clf", lr())]),
        "word_char_tfidf_lr": Pipeline([("tfidf", FeatureUnion([("word", word), ("char", char)])), ("clf", lr())]),
    }


def top_features(model: Pipeline, k: int = 15) -> str:
    """Most positive and most negative words of the word-level model, for the 'what did it learn' check."""
    vec = model.named_steps["tfidf"]
    coef = model.named_steps["clf"].coef_[0]
    names = np.array(vec.get_feature_names_out())
    order = np.argsort(coef)
    neg = ", ".join(f"{names[i]} ({coef[i]:.2f})" for i in order[:k])
    pos = ", ".join(f"{names[i]} ({coef[i]:.2f})" for i in order[::-1][:k])
    return f"Most NEGATIVE features:\n{neg}\n\nMost POSITIVE features:\n{pos}\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, help="labeled CSV")
    ap.add_argument("--out", type=Path, default=Path("results"), help="output folder")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--external-test", type=Path, help="CSV with review_text,label to score every model on (never trained on)")
    ap.add_argument("--predict", type=str, help="score one review with a saved model and exit")
    ap.add_argument("--model", type=Path, default=Path("results/model.joblib"))
    args = ap.parse_args()

    if args.predict is not None:
        model = joblib.load(args.model)
        proba = model.predict_proba([args.predict])[0]
        classes = list(model.classes_)
        print(json.dumps({"text": args.predict, **{c: round(float(p), 3) for c, p in zip(classes, proba)}}, ensure_ascii=False))
        return
    if not args.data:
        ap.error("--data is required unless --predict is used")

    df = load_and_validate(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    X, y = df["review_text"], df["label"]

    # Hold-out split (also used for the confusion matrix) and cross-validation (steadier with small data).
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=args.test_size, stratify=y, random_state=args.seed)
    cv = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)

    # Grouped-by-product CV: reviews of one product share vocabulary, so a random split can leak. Group splits cannot.
    groups, n_groups = None, 0
    if "product_name" in df.columns:
        g = df["product_name"].astype(str).str.strip()
        g = g.where(~g.isin(["", "nan"]))
        if g.notna().all() and g.nunique() >= 4:
            groups, n_groups = g.values, int(g.nunique())
        else:
            print("NOTE: product_name is missing or has fewer than 4 products, so the grouped-by-product check is skipped.")
    else:
        print("NOTE: no product_name column, so the grouped-by-product check is skipped.")

    report, oof_wrong = {}, None
    for name, model in make_models(args.seed).items():
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        cvres = cross_validate(model, X, y, cv=cv, scoring=["accuracy", "f1_macro"])
        report[name] = {
            "holdout_n": int(len(y_te)),
            "holdout_accuracy": round(float(accuracy_score(y_te, pred)), 4),
            "holdout_f1_macro": round(float(f1_score(y_te, pred, average="macro")), 4),
            "holdout_confusion_matrix_rows_true_cols_pred": confusion_matrix(y_te, pred, labels=LABELS).tolist(),
            "cv_folds": args.folds,
            "cv_accuracy_mean": round(float(cvres["test_accuracy"].mean()), 4),
            "cv_accuracy_std": round(float(cvres["test_accuracy"].std()), 4),
            "cv_f1_macro_mean": round(float(cvres["test_f1_macro"].mean()), 4),
        }
        if groups is not None:
            gres = cross_validate(model, X, y, cv=GroupKFold(n_splits=min(args.folds, n_groups)), groups=groups, scoring=["accuracy"])
            report[name]["grouped_cv_n_products"] = n_groups
            report[name]["grouped_cv_accuracy_mean"] = round(float(gres["test_accuracy"].mean()), 4)
            report[name]["grouped_cv_accuracy_std"] = round(float(gres["test_accuracy"].std()), 4)
        print(f"\n== {name} ==")
        print(classification_report(y_te, pred, labels=LABELS, zero_division=0))
        print(f"holdout accuracy {report[name]['holdout_accuracy']:.3f} on {len(y_te)} reviews; "
              f"{args.folds}-fold CV accuracy {report[name]['cv_accuracy_mean']:.3f} +/- {report[name]['cv_accuracy_std']:.3f}")
        if "grouped_cv_accuracy_mean" in report[name]:
            print(f"grouped-by-product CV accuracy {report[name]['grouped_cv_accuracy_mean']:.3f} "
                  f"+/- {report[name]['grouped_cv_accuracy_std']:.3f} over {n_groups} products (unseen products only)")
        if name == "word_char_tfidf_lr":
            oof = cross_val_predict(model, X, y, cv=cv)
            oof_wrong = df.assign(predicted=oof)[oof != y.values]

    # Optional natural test set: train on all rows, score on reviews the models never saw.
    if args.external_test:
        ext = pd.read_csv(args.external_test, dtype=str, keep_default_na=False, encoding="utf-8")
        if not {"review_text", "label"} <= set(ext.columns):
            sys.exit("ERROR: --external-test CSV needs columns review_text and label")
        norm = lambda t: t.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
        ext = ext[ext["label"].isin(LABELS) & (ext["review_text"] != "")]
        overlap = norm(ext["review_text"]).isin(set(norm(df["review_text"])))
        if overlap.any():
            print(f"WARNING: removed {int(overlap.sum())} external test review(s) that also appear in the training data")
            ext = ext[~overlap]
        if len(ext) == 0:
            print("NOTE: the external test file has no usable rows; skipping")
        else:
            ext = ext.reset_index(drop=True)
            report["external_test"] = {"file": str(args.external_test), "n": int(len(ext)),
                                       "label_counts": ext["label"].value_counts().to_dict(), "models": {}}
            print(f"\n== external test: {len(ext)} reviews, labels {ext['label'].value_counts().to_dict()} ==")
            wrong_ext = None
            for name, model in make_models(args.seed).items():
                model.fit(X, y)
                pred = model.predict(ext["review_text"])
                rep_ = classification_report(ext["label"], pred, labels=LABELS, zero_division=0, output_dict=True)
                report["external_test"]["models"][name] = {
                    "accuracy": round(float(accuracy_score(ext["label"], pred)), 4),
                    "negative_recall": round(float(rep_["negative"]["recall"]), 4),
                    "negative_precision": round(float(rep_["negative"]["precision"]), 4),
                    "positive_recall": round(float(rep_["positive"]["recall"]), 4),
                    "confusion_matrix_rows_true_cols_pred": confusion_matrix(ext["label"], pred, labels=LABELS).tolist(),
                }
                m = report["external_test"]["models"][name]
                print(f"{name:22s} accuracy {m['accuracy']:.3f}  negative recall {m['negative_recall']:.3f}  negative precision {m['negative_precision']:.3f}")
                if name == "word_char_tfidf_lr":
                    wrong_ext = ext.assign(predicted=pred)[pred != ext["label"].values]
            if wrong_ext is not None:
                wrong_ext.to_csv(args.out / "misclassified_external.csv", index=False, encoding="utf-8")
                print(f"Wrote misclassified_external.csv ({len(wrong_ext)} wrong). Read these by hand.")

    # Final model: the best configuration, refit on ALL labeled rows, saved for the app.
    final = make_models(args.seed)["word_char_tfidf_lr"].fit(X, y)
    joblib.dump(final, args.out / "model.joblib")
    word_only = make_models(args.seed)["word_tfidf_lr"].fit(X, y)
    (args.out / "top_features.txt").write_text(top_features(word_only), encoding="utf-8")
    oof_wrong.to_csv(args.out / "misclassified.csv", index=False, encoding="utf-8")
    meta = {"rows": int(len(df)), "class_counts": df["label"].value_counts().to_dict(), "seed": args.seed,
            "data_file": str(args.data), "models": report}
    (args.out / "metrics.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote metrics.json, misclassified.csv ({len(oof_wrong)} cross-validated errors), "
          f"top_features.txt and model.joblib to {args.out}/")
    print("Next: read misclassified.csv by hand and describe the error patterns in your report.")


if __name__ == "__main__":
    main()
