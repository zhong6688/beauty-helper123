# Collecting and labeling reviews

Read [DATA_FORMAT.md](DATA_FORMAT.md) first for the columns and the two kinds of review (`kb` and `train`).

## Collecting

- **Copy by hand** the text of public reviews you read. Do not run an automatic scraper: marketplace terms usually forbid it, and 15 products
  do not need one. Check each platform's terms if unsure.
- **Review text only.** Leave out usernames, profile names, photos, order details and anything that identifies a person.
- **Per product page (`kb`):** copy the first ~15 reviews in the order the page shows them. If the platform offers "newest first", you may
  use it, but use the same setting for every product and say so in your report. Do not skip the boring or the positive ones.
- **For the classifier (`train`):** collect matched pairs within each product: as many positive PRODUCT reviews (4-star and 5-star filter) as
  negative PRODUCT reviews (1-star and 2-star filter). This keeps the product name from telling the model the label (a first check on
  real data showed that when one product is all negative and another mostly positive, the model learns the product). Reviews that are about
  the product are scarce among negatives: in the first batches only about a third of the 1-2 star reviews were about the product, the rest
  complained about delivery and packaging. So you need MANY products, not many reviews from one product. Training reviews may come from any
  cosmetic or skincare product (your plan says cosmetic reviews), not only moisturizers; give those products `role = train_only` in the products
  table. Sunscreens, serums and cleansers often have more complaints about the product itself. Use at least 6 products. Leave out 3-star
  reviews at first (mixed, hard to label).
- **Only reviews about the product itself.** Skip reviews that only talk about delivery, packaging, the seller, price or authenticity
  (`usable = no`). A model trained on them learns "fast delivery means positive" and "poor, not, shop means negative", which says
  nothing about whether a moisturizer suits someone's skin.
- Keep reviews in Singlish, Chinese, or mixed language. Your plan says to include local phrasing; those are where models fail.
- Record price, date and product page in the products table as you go; prices on marketplaces change and are often on sale, so note the
  regular price and the date.

## Labeling (your own work; the course asks for hand labeling)

| Situation | What to do |
| --- | --- |
| Satisfied, would recommend | `positive` |
| Bad outcome (irritation, breakout, no effect, regret) or would not buy again | `negative` |
| Mixed ("works but smells awful") | Follow the reviewer's overall verdict; use the star rating only to break a tie |
| "Not tried yet", sarcasm, or you cannot decide | `usable = no` and write `skip_reason`; count how many you skipped |
| Only about delivery, packaging, seller, price or authenticity | `aspect = service` (and `usable = no`); never used for training |
| Talks about the product (skin, texture, smell, results) | `aspect = product` |

## Your kb reviews become the test set

The classifier is trained only on `train` reviews, which you chose by star filter. The `kb` reviews are the ones the assistant will really
meet, so label the usable ones by hand too: the script keeps them apart as `kb_labeled_test.csv`, and the classifier is scored on them without
ever training on them. Expect few negatives there; that is normal and is exactly why the test is informative.

## Check yourself

Pick 30 reviews at random, hide the labels, and relabel them a day later. The share that changes is a rough estimate of label noise, and a
good sentence for your evaluation critique.

## Biases to mention in your report

- The balanced 1:1 training set is not the real mix of reviews, which is mostly positive: the classifier's precision on a real stream will differ.
- Platform default order tends to show positive reviews first, so every product's share of positive reviews is high and says little about
  which product is better. Skin-type label, price and ingredients carry most of the recommendation.
- Both labels for training were picked on purpose (by star filter), from products that happen to have many reviews of each kind.
