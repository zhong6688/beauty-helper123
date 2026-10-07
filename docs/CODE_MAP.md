# Code map (for people and for AI agents reading the repository)

**Entry points**

| Goal | Command or file |
| --- | --- |
| Use the product | `app/index.html` (published as a Claude artifact; see `README.md`) |
| Rebuild the page | `python scripts/build_app.py` (reads `data/`, `results/model.joblib`, `app/model.json`, `evals/app_eval_questions.json`; writes `app/kb.json`, `app/index.html`) |
| Retrain the classifier | `python scripts/train_classifier.py --data data/reviews_labeled.csv --out results/` then `python scripts/export_model.py` |
| Test everything that does not call Claude | `node tests/test_app_logic.js` and `node tests/test_page_flow.js` |
| Estimate the tokens each question sends to the model | `node scripts/estimate_tokens.js` |

**Data flow:** `data/products.csv` + reviews (`data/reviews.csv`, `data/reviews_labeled.csv`, `data/pending_new_rows.csv`) -> `scripts/build_app.py` (tags reviews: hand label
where it exists, otherwise the classifier) -> `app/kb.json` -> inlined with `app/model.json`, `app/logic.js`, `app/template.html` -> `app/index.html`.

**Modules**

| File | Responsibility |
| --- | --- |
| `app/logic.js` | Pure functions, no page and no network: `classify` (sklearn re-implemented), `parseNeed`, `outOfScope`, `selectCandidates`, `pickReviews`, `buildPrompt`, `verifyAnswer` |
| `app/template.html` | Page markup and page code: `recommend` (the whole pipeline for one message), rendering, Products, Classifier and Evaluation tabs (`runEval`, `autoCheck`) |
| `scripts/build_app.py` | Builds the knowledge base and the single-file page |
| `scripts/export_model.py` | Exports the scikit-learn model to JSON and writes `tests/parity_cases.json` |
| `scripts/train_classifier.py` | Trains and evaluates the classifier |
| `scripts/check_data.py`, `scripts/import_batches.py`, `scripts/audit_reviews.py`, `scripts/make_template.py` | Data preparation helpers used while collecting reviews |
| `tests/` | `test_app_logic.js` (classifier parity, routing of the evaluation questions, guardrails), `test_page_flow.js` (page code with a pretend model) |

**Conventions:** every script and `logic.js` start with a header comment describing purpose and usage. Facts shown to the shopper (price, link, skin types) are read from the knowledge base,
never from the model. Quotes are checked against the stored review text.
