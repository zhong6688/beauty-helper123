/**
 * Tests for app/logic.js with no network and no Claude: run  node tests/test_app_logic.js
 *   1. the JavaScript classifier gives the same probabilities as sklearn (tests/parity_cases.json)
 *   2. parsing the shopper's message, scope detection and candidate selection give the expected results for the app's evaluation questions
 *   3. the guardrails reject made-up quotes, products outside the candidates, over-budget picks, medical claims and unsupported property claims
 */
const fs = require("fs"), path = require("path");
const L = require("../app/logic.js");
const kb = JSON.parse(fs.readFileSync(path.join(__dirname, "../app/kb.json"), "utf8"));
const model = JSON.parse(fs.readFileSync(path.join(__dirname, "../app/model.json"), "utf8"));
const parity = JSON.parse(fs.readFileSync(path.join(__dirname, "parity_cases.json"), "utf8"));
const evals = JSON.parse(fs.readFileSync(path.join(__dirname, "../evals/app_eval_questions.json"), "utf8"));
let pass = 0, fail = 0;
const ok = (cond, msg) => { if (cond) pass++; else { fail++; console.log("FAIL:", msg); } };

// 1. classifier parity
let maxDiff = 0, worst = null;
for (const c of parity) { const d = Math.abs(L.classify(model, c.text) - c.p_positive); if (d > maxDiff) { maxDiff = d; worst = c.text; } }
ok(maxDiff < 1e-6, `classifier parity: max difference ${maxDiff} on "${worst}"`);
console.log(`classifier parity on ${parity.length} texts: max abs difference ${maxDiff.toExponential(2)}`);

// 2. routing of the evaluation questions
for (const e of evals) {
  const need = L.parseNeed(e.question), scope = L.outOfScope(e.question);
  let status;
  if (scope) status = "out_of_scope";
  else if (!need.skin.length) status = "needs_info";
  else status = L.selectCandidates(kb, need, e.question).length ? "candidates" : "no_match";
  const wanted = e.expect_status === "recommend" || e.expect_status === "any" ? "candidates" : e.expect_status;
  ok(status === wanted, `Q${e.id} routing: got ${status}, wanted ${wanted} (${e.question})`);
  if (status === "candidates") {
    const ids = L.selectCandidates(kb, need, e.question).map(p => p.product_id).sort();
    const bad = e.expect_status === "any" || e.id === 7 ? [] : ids.filter(i => !e.eligible.includes(i));
    ok(bad.length === 0, `Q${e.id} candidates ${ids} include products outside the eligible set ${e.eligible}`);
    if (e.id !== 7 && e.expect_status !== "any") ok(e.eligible.every(i => ids.includes(i)) || ids.length === 3, `Q${e.id} candidates ${ids} miss eligible ${e.eligible}`);
  }
  ok(need.medical === e.needs_medical_notice, `Q${e.id} medical flag ${need.medical}`);
}
const n = L.parseNeed("Oily skin, budget S$5.");
ok(n.budget === 5 && n.skin.includes("oily"), "budget parsing S$5");
ok(L.parseNeed("under 30 dollars, dry skin").budget === 30, "budget 'under 30 dollars'");
ok(L.parseNeed("something", { skin: "dry", budget: "12" }).skin.includes("dry") && L.parseNeed("something", { budget: "12" }).budget === 12, "dropdown overrides");
ok(L.outOfScope("moisturizer to wear under sunscreen") === null, "moisturizer + sunscreen mention stays in scope");
ok(L.outOfScope("which serum is best?") === "soft", "serum alone is out of scope");

// 3. guardrails with a pretend model
const need = L.parseNeed("Dry skin, my budget is S$40.");
const cands = L.selectCandidates(kb, need, "dry skin");
const rbp = Object.fromEntries(cands.map(p => [p.product_id, L.pickReviews(kb, p, "dry skin", 5)]));
const ctx = { candidates: cands, need, reviewsByProduct: rbp };
const pick = cands[0], rev = rbp[pick.product_id][0];
const words = rev.text.split(/\s+/).slice(0, 6).join(" ");
let v = L.verifyAnswer({ status: "recommend", pick: pick.product_id, reason: "The brand says it hydrates. One reviewer says it feels soft.", quotes: [{ review_id: rev.id, quote: words }], caveats: ["Patch test first."], alternatives: [] }, ctx);
ok(v.status === "recommend" && v.quotes.length === 1 && v.rejectedQuotes === 0, "valid answer accepted");
v = L.verifyAnswer({ status: "recommend", pick: pick.product_id, reason: "Good.", quotes: [{ review_id: rev.id, quote: "this exact sentence was never written by anybody" }] }, ctx);
ok(v.quotes.length === 0 && v.rejectedQuotes === 1, "made-up quote rejected");
v = L.verifyAnswer({ status: "recommend", pick: "P99", reason: "x", quotes: [] }, ctx);
ok(v.status === "no_match", "pick outside candidates rejected");
const costly = kb.products.find(p => p.product_id === "P03");   // S$36
v = L.verifyAnswer({ status: "recommend", pick: "P03", reason: "x" }, { candidates: [costly], need: { budget: 20, skin: ["oily"] }, reviewsByProduct: { P03: [] } });
ok(v.status === "no_match", "over-budget pick rejected");
v = L.verifyAnswer({ status: "recommend", pick: pick.product_id, reason: "It cures your eczema. It hydrates well.", quotes: [] }, ctx);
ok(v.medicalClaimBlocked && !/cure/i.test(v.reason) && /hydrates/.test(v.reason), "medical claim removed, rest kept");
const torr = kb.products.find(p => p.product_id === "P01");
v = L.verifyAnswer({ status: "recommend", pick: "P01", reason: "It is fragrance-free and light." , quotes: [] }, { candidates: [torr], need: { budget: null, skin: [] }, reviewsByProduct: { P01: [] } });
ok(v.unsupportedClaimsBlocked === 1 && !/fragrance/i.test(v.reason), "unsupported fragrance-free claim for Torriden removed");
const cera = kb.products.find(p => p.product_id === "P05");
v = L.verifyAnswer({ status: "recommend", pick: "P05", reason: "The page states it is fragrance-free." , quotes: [] }, { candidates: [cera], need: { budget: null, skin: [] }, reviewsByProduct: { P05: [] } });
ok(v.unsupportedClaimsBlocked === 0 && /fragrance/i.test(v.reason), "stated fragrance-free claim for CeraVe kept");
v = L.verifyAnswer({ status: "recommend", pick: pick.product_id, reason: `${pick.product_id} fits best. It is cheaper than ${cands[1] ? cands[1].product_id : "P99"}.`, quotes: [], caveats: [`Check ${pick.product_id} first.`] }, ctx);
ok(!/\bP\d{2}\b/.test(v.reason) && v.reason.includes(pick.product_name.replace(/\s*\(.*?\)\s*$/, "")) && !/\bP\d{2}\b/.test(v.caveats.join(" ")), "product codes replaced by names");
v = L.verifyAnswer(null, ctx);
ok(v.status === "no_match" && v.notes.length === 1, "null answer handled");
const prompt = L.buildPrompt("Dry skin", need, cands, rbp);
ok(prompt.includes(cands[0].product_name) && prompt.includes(rev.id), "prompt contains product and review ids");

console.log(`\n${pass} checks passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
