# Data used

All data was collected by the author from public Shopee Singapore product pages (screenshots and copy-paste). No automatic scraping was used. Reviewer names and other
personal details were not copied.

| File | What it is |
| --- | --- |
| `products.csv` | The 7 knowledge-base moisturizers: name, price seen (SGD) and date, size, link, skin types listed on the page, brand claims, description, ingredients, and a `my_note` column with caveats |
| `reviews.csv` | Reviews copied from product pages in page order, with the author's classification (`aspect` product or service, `usable`, reason) |
| `reviews_labeled.csv` | 121 reviews about the products themselves with the author's hand label (positive or negative); the classifier's training data; also the source of reviews for two products |
| `pending_new_rows.csv` | One more labeled review not yet used for training |
| `excluded_products.md` | Candidate products that were screened out and why |
| `products_template.csv`, `reviews_template.csv`, `beauty_helper_data_template.xlsx` | Empty templates used to organize the data |
| `audit/audit_flags_first_batches.csv` | Keyword-rule flags for the first five review batches (delivery-only, not tried, non-English ...) |

How it was prepared: of 223 reviews collected for the classifier, 101 were removed (duplicates, reviews only about delivery, packaging, seller, price or authenticity,
reviews of 3 words or fewer, and reviews with Tagalog or Malay words or other-country prices). See `../results/NOTES.md`.

The classifier in `../results/` was trained on `reviews_labeled.csv` as it is (all 121 usable reviews, not matched per product). `../scripts/check_data.py` can also produce a version matched within each product in `data/processed/`; on products the model had not seen, both gave the same pooled accuracy (83.5%).

## Things to know

- Prices are what the author saw on 2026-10-07 during a sale (10.10), not regular prices. Where the regular price was visible it is in `my_note`.
- Reviews are not a random sample. Some were copied in page order (`reviews.csv`); the classifier data was partly picked by star filter. Positive and negative counts
  are not a measure of product quality. Most of the first review pages of every product are 4 and 5 stars.
- Skin types come from the product page. "All skin types" is not counted as a specific type. Two labels are judgments and are marked as such in `my_note`
  (Torriden: sensitive; Himalaya: dry, derived from its headline claim).
  The assistant's quote check compares quotes with the text stored in this repository, not with the live page.
- Product pages change; the data is a snapshot.
