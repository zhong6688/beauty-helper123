# Data format: the two tables

Fill `data/beauty_helper_data_template.xlsx` (drop-down lists included) or the CSV templates `data/products_template.csv` and
`data/reviews_template.csv`. Then run `python scripts/check_data.py --workbook data/beauty_helper_data.xlsx`.

## Scope decisions (fixed, so the data stays consistent)

- **Category:** face moisturizers sold in Singapore. Not covered: anti-ageing or whitening products, sunscreens, tinted products, eye creams, masks.
- **Products:** 15, in three price tiers of 5 (tiers are set from your actual prices by the script, as thirds).
- **One skin-type label per product:** oily (wants light and fresh), dry (wants rich and nourishing), or sensitive (wants soothing and fragrance-free).
  Take it from the official product page's first and most prominent claim, not from your own feeling. Other claims stay in the text columns.
- **Coverage:** every price tier should contain more than one skin type, otherwise price and skin type cannot be told apart in the evaluation.

## `products` table (one row per product)

| Column | Meaning |
| --- | --- |
| `product_id` | `P01`, `P02` ... |
| `product_name`, `brand`, `size` | As on the page, e.g. `50ml` |
| `role` | `kb`: a moisturizer the assistant may recommend (about 15; needs price, skin type, main claim). `train_only`: any other cosmetic product whose reviews you use only to train the classifier (needs just id, name, platform, role) |
| `platform`, `url` | Where you read it (Shopee, Lazada, Sephora SG) and the page address |
| `price_sgd`, `price_date` | Regular (not sale) price as a number, and the date you noted it |
| `skin_type_label` | `oily`, `dry` or `sensitive` |
| `official_skin_type_text`, `official_benefits_text` | The page's own wording, copied |
| `main_claim` | The first and most prominent benefit, in a few words |
| `description`, `ingredients` | Page text; the full ingredient list if shown |

## `reviews` table (one row per review)

| Column | Meaning |
| --- | --- |
| `review_id` | `R0001`, `R0002` ... |
| `product_id` | Must exist in the products table |
| `platform` | Where you copied it |
| `review_text` | The text only. No usernames, photos or personal details. Platform fields such as "Moisture: ..." can stay inside the text |
| `rating` | 1 to 5 if shown, else empty |
| `use` | `kb` or `train` (see below) |
| `aspect` | `product` if the review is about the product itself (skin, texture, smell, results); `service` if it is only about delivery, packaging, the seller, price or authenticity. Only `product` reviews are ever used |
| `label` | **Your** hand label: `positive` or `negative`. Required for usable `train` rows; recommended for `kb` rows |
| `usable` | `yes`, or `no` for "not tried yet" or reviews you cannot decide (service reviews are `no` too) |
| `skip_reason` | Why it is `no` |
| `source` | For example `manual-copy 2026-10-12` |

## Two kinds of review, kept apart

| | `use = kb` | `use = train` |
| --- | --- | --- |
| What | The first ~15 reviews on the product page, copied in page order | Reviews picked on purpose, mostly 1 to 3 star |
| Selected by you? | **No.** Copy them as they come, even if they are all positive | Yes, by star filter |
| Used for | What the assistant reads; the "share of positive reviews" per product; if you hand-label them, the classifier's natural **test set** (never trained on) | Training the classifier only |
| Per product | About 15 copied, usually 8 to 12 usable | As many positive as negative PRODUCT reviews from the SAME product (matched pairs); any cosmetic product; at least 6 products overall |

Never add hand-picked negatives to `kb`: products you searched harder would look worse than products you did not.

## What the script produces

`products_with_tiers.csv`, `reviews_labeled_all.csv` and `reviews_labeled.csv` (the `train` reviews, matched within each product so positives = negatives, for `train_classifier.py`),
`kb_labeled_test.csv` (your hand-labeled `kb` reviews, the natural test set) and `data_report.md` (counts, coverage, warnings) in `data/processed/`.
Products with only one label are left out of the training file, and surplus positives or negatives are dropped per product, because otherwise the product name leaks the label.

## Fictional examples of one row (for format only)

```
products: P01,Example Gel Cream,ExampleBrand,50ml,Shopee,https://example.invalid/p01,24.90,2026-10-12,oily,"Oily, combination","Hydrating, oil-free",Lightweight hydration,"A gel-cream ...","Water, Glycerin, ..."
reviews:  R0001,P01,Shopee,"Light and not sticky, good for humid weather",5,kb,product,positive,yes,,manual-copy 2026-10-12
reviews:  R0102,P03,Lazada,"Got pimples after a week, waste of money",1,train,product,negative,yes,,manual-copy 2026-10-13
reviews:  R0103,P03,Lazada,"Have not tried yet, will update",,kb,product,,no,not used yet,manual-copy 2026-10-13
reviews:  R0104,P03,Lazada,"Fast delivery, well packed",5,kb,service,,no,service only,manual-copy 2026-10-13
```
