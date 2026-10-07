/**
 * Estimates how many tokens each assistant question sends to the model, with no network and no Claude: node scripts/estimate_tokens.js
 *
 * It builds the same prompt the page builds for each evaluation question and counts characters. Tokens are estimated as characters / 4, a rough rule for English text:
 * the real tokenizer is not available here, so treat the numbers as +/- 25%. Questions answered by code (missing skin type, out of scope, no match) send nothing.
 * The sentiment classifier runs in the browser and uses no model tokens. The answer's size (output tokens) is estimated on the page from the JSON the model returns.
 */
const fs = require("fs"), path = require("path");
const L = require("../app/logic.js");
const kb = JSON.parse(fs.readFileSync(path.join(__dirname, "../app/kb.json"), "utf8"));
const evals = JSON.parse(fs.readFileSync(path.join(__dirname, "../evals/app_eval_questions.json"), "utf8"));
const rows = [];
for (const e of evals) {
  const need = L.parseNeed(e.question);
  if (L.outOfScope(e.question) || !need.skin.length) { rows.push({ id: e.id, route: "code only", tokens: 0 }); continue; }
  const cands = L.selectCandidates(kb, need, e.question);
  if (!cands.length) { rows.push({ id: e.id, route: "code only", tokens: 0 }); continue; }
  const rbp = Object.fromEntries(cands.map(p => [p.product_id, L.pickReviews(kb, p, e.question, 5)]));
  const prompt = L.buildPrompt(e.question, need, cands, rbp);
  rows.push({ id: e.id, route: `model (${cands.length} products)`, chars: prompt.length, tokens: Math.ceil(prompt.length / 4) });
}
console.table(rows);
const m = rows.filter(r => r.tokens > 0).map(r => r.tokens);
console.log(`questions sent to the model: ${m.length} of ${rows.length}; estimated input tokens per question: min ${Math.min(...m)}, mean ${Math.round(m.reduce((a, b) => a + b, 0) / m.length)}, max ${Math.max(...m)}`);
console.log("estimated total input tokens for the 14 questions:", m.reduce((a, b) => a + b, 0));
