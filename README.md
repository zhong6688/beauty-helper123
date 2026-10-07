# Beauty Helper

An assistant that recommends a **face moisturizer** to first-time shoppers and gift givers in Singapore, based on skin type and budget, and backs the
recommendation with real reviews. Course project (PE6201). The knowledge base is small on purpose: 7 everyday moisturizers from Shopee Singapore, priced roughly S$5 to S$42 on 2026-10-07 (sale prices).

- **Live demo (needs a Claude account, see "How to run")**: https://claude.ai/artifact/GagUi66WRnviDTDJs5X5w3
- **Report** (business and technical trade-off analysis): [docs/REPORT.pdf](docs/REPORT.pdf) (also `REPORT.docx`, `REPORT.md`). **Product documentation**: [docs/PRODUCT.md](docs/PRODUCT.md).

## The three parts, in one pipeline

| Part | What | How | Where |
| --- | --- | --- | --- |
| 1 | Review sentiment classifier | scikit-learn: word and character TF-IDF with logistic regression, trained on 121 hand-labeled reviews about the products themselves | `scripts/train_classifier.py`, `results/` |
| 2 | Retrieve what is relevant | Own code: filters products by budget and by the skin types listed on their product pages, then picks review excerpts, always including critical ones | `app/logic.js` |
| 3 | Write the recommendation | Claude (through the Claude artifact runtime), then own code checks every quote and claim | `app/logic.js`, `app/template.html` |

The classifier connects to the rest in two ways: it tags knowledge-base reviews that have no hand label, and it runs in the page ("Review classifier" tab),
re-implemented in JavaScript and tested to give the same probabilities as scikit-learn (difference about 1e-10).

## How to run

**Option A: the live page.** Open the link above. It needs a Claude account (the model call runs on the viewer's own account) and the page must be shared with the viewer.
The first question asks for permission to use Claude; choose Allow. Try the example questions; open the Evaluation tab and press *Run evaluation*.

**Option B: tests that need no account and no network** (Node.js 18 or newer):
```
node tests/test_app_logic.js     # classifier parity with sklearn, routing of the 14 evaluation questions, all guardrails
node tests/test_page_flow.js     # runs the page code end to end with a pretend model
```
These do not call Claude; they test everything around it. The model's real behaviour is checked by the Evaluation tab of the live page.

**Option C: rebuild the page from the data** (Python 3, `pip install scikit-learn pandas joblib openpyxl`):
```
python scripts/train_classifier.py --data data/reviews_labeled.csv --out results/
python scripts/export_model.py
python scripts/build_app.py          # writes app/kb.json and app/index.html
```

## Files

| Path | What |
| --- | --- |
| `app/template.html`, `app/logic.js` | The page and its logic (parsing, routing, retrieval, prompt, guardrails, classifier) |
| `app/index.html` | The built single-file page (knowledge base, model and logic inlined) |
| `app/kb.json`, `app/model.json` | The knowledge base and the exported classifier |
| `data/products.csv` | The 7 knowledge-base products, with price, skin types listed on the page, claims, description, ingredients, and notes |
| `data/reviews.csv`, `data/reviews_labeled.csv`, `data/pending_new_rows.csv` | Reviews: copied from product pages, the hand-labeled classifier data, and one extra labeled row |
| `data/excluded_products.md` | Products that were screened out and why |
| `evals/app_eval_questions.json` | The 14 scenario questions for the assistant |
| `results/` | Classifier metrics, mistakes, top words, and `NOTES.md` explaining the data and its limits |
| `scripts/` | Data checks, import, classifier training, export, page build, `estimate_tokens.js` (prompt size per question); `check_data.py` and `import_batches.py` were used to prepare the tables |
| `tests/` | Node tests and a retrieval/parity test file |
| `docs/` | `PRODUCT.md` (persona, input, output, architecture, metrics targeted and reached), `DEMO_SCRIPT.md`, `CODE_MAP.md`, data format and labeling guide, the report |
| `evals/README.md`, `data/README.md` | Explainers for the evaluations (including the harness) and for the data |

## Honest notes

- Prices are what the author saw on Shopee Singapore on 2026-10-07 during a sale, not regular prices. Pyunkang Yul's size is assumed (50ml), and several products have no full ingredient list (their pages give only the main ingredients).
- Reviews are not a random sample (some copied in page order, some picked by star filter); positive and negative counts do not show how good a product is.
- Many negative reviews are about delivery and packaging; only reviews about the product itself were used for the classifier (122 of 223 collected; 121 used for training).
- "All skin types" on a page is not treated as a match for a specific skin type. Torriden's skin-type label is a judgment (see the note in `products.csv`).
- The classifier misses about a third of negative reviews (details in `results/NOTES.md`).
- Assistant evaluation, run 1: 14 of 14 scenario questions pass the automatic checks (`evals/results/app_eval_run1.json`). This is weak evidence: the checks are lenient, the questions were written after the data was collected, and 6 of 9 picks were CeraVe (the product with the most reviews). See `evals/README.md`.
- Not medical advice; the assistant declines to claim a product treats a condition.
