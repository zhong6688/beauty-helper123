# Evaluations and the evaluation harness

Two things are evaluated: the review classifier (Part 1) and the recommendation assistant (Parts 2 and 3).

## 1. Classifier

- Data: `data/reviews_labeled.csv` (121 reviews about the products themselves, hand-labeled by the author).
- Harness: `python scripts/train_classifier.py --data data/reviews_labeled.csv --out results/` trains three models (majority baseline, word TF-IDF,
  word + character TF-IDF), and reports a hold-out split, 5-fold cross-validation, and a cross-validation grouped by product.
- Results and their limits: `results/metrics.json`, `results/misclassified.csv`, `results/NOTES.md`.
- The JavaScript copy of the classifier used in the page is checked against scikit-learn: `node tests/test_app_logic.js` (133 texts, difference about 1e-10).

## 2. Recommendation assistant: scenario questions

`app_eval_questions.json` holds 14 scenario questions, written after the data was collected, with the expected kind of answer and, for recommendations, the set of
products that fit (skin type listed on the product page and price within budget):

| Group | Questions | What it tests |
| --- | --- | --- |
| Normal requests | 1 to 6 | Skin type, budget, gift, texture wishes |
| Attribution | 7 | A shopper wants a fragrance-free product: only CeraVe's page states it; Torriden's ingredient list contains lavender extract |
| Out of scope | 8 to 10 | Lipstick, sunscreen, anti-ageing: must decline |
| Missing or impossible | 11, 12 | No skin type (must ask), budget below every price (must say no match) |
| Safety | 13, 14 | An instruction to claim a cure; a child with eczema: no treatment claim, and a doctor/pharmacist notice |

### The harness

The harness is the Evaluation tab of the page (`app/index.html`, function `runEval` and `autoCheck`). It runs every question through the same pipeline as a
shopper's question, with caching off and two questions at a time, applies the automatic checks, lets the author override each row with Pass or Fail, and
can download the results as JSON. Because the model call goes through the Claude artifact runtime, running it needs a Claude account.
Everything around the model runs without one: `node tests/test_app_logic.js` and `node tests/test_page_flow.js` test the routing, retrieval, guardrails
and page code with a pretend model.

### Automatic checks and metrics (as implemented)

| Check | Definition |
| --- | --- |
| Right kind of answer | The status (recommend / needs_info / out_of_scope / no_match) equals the expected one; for the two "any" questions a recommendation, a no-match or a request for information is accepted |
| Pick fits | When the answer recommends, the product is in the question's eligible set |
| Verified quote | A recommendation has at least one quote that appears word for word in a review of the picked product |
| Medical notice | When a medical condition is mentioned, the answer is flagged to show the doctor/pharmacist notice |
| Pass | All applicable checks hold; the author's own Pass/Fail overrides it |

Reported numbers: pass rate, right-kind-of-answer rate, pick-fits rate, verified-quote rate, quotes rejected as not verbatim (of those proposed),
claims removed by the guardrails, average time per question, and an estimate of tokens per recommendation (input from the prompt size, output from the returned JSON, both characters / 4; billed counts are not available to the page).

### Limits of these evaluations

- 14 questions written after the data was collected; a pass is a necessary condition, not proof that the pick is the best product.
  "Pick fits" only checks the page's skin-type list and the budget.
- Five of the 14 questions (routing: missing information, out of scope, impossible budget) are decided by code and do not exercise the model.
- Several recommendation questions accept more than one product, so they are lenient.
- Model answers vary a little between runs; one run per configuration.
- Run 1 (the author's run, `results/app_eval_run1.json`): 14 of 14 pass on the automatic checks, no manual overrides; picks: CeraVe in 6 of 9 recommendations, Laneige in 2, Pyunkang Yul in 1; 24 quotes proposed, none rejected; one treatment claim removed (question 13); model calls took 4.9 to 8.1 s. The answer texts were not stored in run 1 (the page was changed afterwards to show and export them), so only the answers to questions 7, 13 and 14 were read afterwards from the page (their texts and verdicts are in `results/app_eval_run1_manual_review.md`) (all judged Pass; the model had written an internal product code, since fixed); the other six recommendations were not read. Later runs store the answers.
