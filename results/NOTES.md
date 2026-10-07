# Classifier results: how they were made and how to read them

## Data
- Collected by hand: 223 reviews (109 positive, 114 negative) from 5 products (The Ordinary serum, CeraVe cream, Dr. Althea 345, Torriden, Dr. Reju-All),
  in 8 batches. Positive and negative labels are the author's.
- Removed before training (keyword rules in `scripts/audit_reviews.py` for the first five batches; hand-checked suggestions for the last two):
  10 exact duplicates; reviews that only talk about delivery, packaging, the seller, price or authenticity; reviews of 3 words or fewer;
  reviews with Tagalog or Malay words or an other-country price. 101 reviews removed.
- Left for training: **121 reviews (82 positive, 39 negative)**, `data/reviews_labeled.csv`. This is below the 150 to 200 planned. One more usable negative review (from the last Torriden batch) is kept in `data/pending_new_rows.csv` and was not used for training.
- The first five batches were NOT checked by hand review by review; the keyword rules make mistakes in both directions.
- Product names for the first five batches were assigned by batch and by keywords (batch 4 mixed CeraVe and Dr. Althea reviews).
- Positives and negatives are not matched per product (Dr. Althea has no positives; CeraVe has 45 positive and 9 negative).
  Training on matched pairs only (56 rows) gave the same pooled accuracy on unseen products (83.5% both ways), so all 121 were kept.

## Results (best model: word + character TF-IDF, logistic regression)
| Test | Accuracy | Guessing the majority class |
| --- | --- | --- |
| Hold-out, 25 reviews | 88% | 68% |
| 5-fold cross-validation | 87% +/- 5 | 68% |
| Grouped by product (the test product was never seen), 5 products | 76% +/- 16 | 59% |

- 16 of 121 reviews were wrong in cross-validation; 14 of them were negative reviews predicted as positive (negative recall about 64%).
- The most positive words include "delivery" and "fast delivery", and "not as described" is among the most negative: some delivery and seller
  language from mixed reviews still leaks into what the model learned.
- One review is 4 points on the hold-out set and the grouped result swings widely by product (see `metrics.json`): treat all figures as rough.

## Why data collection stopped at 121 usable reviews
- 114 negative reviews were collected in total; only 40 of them (about 35%) described the product's effect on skin (121 rows in the training
  file plus 1 more saved in `data/pending_new_rows.csv`, not yet trained on). The rest complained about delivery, packaging, the seller, price or
  authenticity, or said the reviewer had not tried the product.
- Torriden is typical: 5 of its 21 collected negatives were about the product.
- Rather than weaken the rule for what counts as a product review, collection was stopped at 121 usable reviews (plan: 150 to 200).
  This is enough to train and compare a baseline classifier; it is not enough for strong claims, and the evaluation limits are listed above.
