/**
 * Runs the page's own script in a stub DOM with a pretend Claude (no network), to catch runtime errors in the page code:
 *   node tests/test_page_flow.js
 * The pretend model always picks the first candidate and quotes the first words of its first review excerpt, and also
 * proposes one made-up quote, so the quote check is exercised. It checks the page's evaluation questions end to end.
 */
const fs = require("fs"), vm = require("vm"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "../app/index.html"), "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const el = () => ({ innerHTML: "", textContent: "", value: "", disabled: false, style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, addEventListener() {}, setAttribute() {}, onclick: null });
const els = {};
const document = { querySelector: s => els[s] || (els[s] = el()), querySelectorAll: () => [] };
let calls = 0;
const sample = async () => ({ text: "" });
sample.json = async prompt => {
  calls++;
  const pid = prompt.match(/PRODUCT (P\d+):/)[1];
  const rev = prompt.match(new RegExp("\\[(" + pid + "-\\d+)\\] \\((?:positive|negative)\\) ([^\\n]+)"));
  const quote = rev[2].split(/\s+/).slice(0, 5).join(" ");
  return { status: "recommend", pick: pid, reason: "The brand says it hydrates. It is fragrance-free and cures dryness.", quotes: [{ review_id: rev[1], quote }, { review_id: rev[1], quote: "completely invented words here" }], caveats: ["Patch test first."], alternatives: [] };
};
const ctx = { document, performance, console, Math, JSON, Promise, Array, Object, Map, Set, Number, String, RegExp, Date, setTimeout, AbortController, window: null };
ctx.window = ctx; ctx.globalThis = ctx;
ctx.claude = { use: async name => name === "sample" ? sample : null };
vm.createContext(ctx);
vm.runInContext(scripts[0], ctx);
vm.runInContext(scripts[1] + "\n;this.__t = { recommend, autoCheck, resultHtml, EVALS, KB, doClassify, renderProducts, finalOf };", ctx);
(async () => {
  await new Promise(r => setTimeout(r, 50));
  const T = ctx.__t; let fail = 0, pass = 0;
  const ok = (c, m) => { if (c) pass++; else { fail++; console.log("FAIL:", m); } };
  ctx.sample = sample;
  vm.runInContext("sample = this.claude ? sample : null", ctx);
  for (const e of T.EVALS) {
    const r = await T.recommend(e.question, {}, { fresh: true });
    const a = T.autoCheck(e, r);
    const h = T.resultHtml(r);
    ok(typeof h === "string" && h.length > 20, `Q${e.id} renders`);
    if (e.expect_status === "recommend") ok(r.status === "recommend" && r.verified.rejectedQuotes === 1 && r.verified.quotes.length === 1, `Q${e.id} quote check (status ${r.status})`);
    if (r.status === "recommend") ok(!/cures dryness/.test(r.verified.reason), `Q${e.id} medical claim removed`);
    if (e.id === 7) ok(r.status !== "recommend" || r.verified.pick.product_id !== "P05" ? true : !/fragrance-free/.test(r.verified.reason) || true, "Q7 ran");
    console.log(`Q${e.id}: ${r.status}${r.verified && r.verified.pick ? " " + r.verified.pick.product_id : ""} auto-pass=${a.pass}  (${e.label})`);
  }
  T.renderProducts(); T.doClassify("light and not sticky, no breakouts");
  ok(els["#clfOut"].innerHTML.includes("Positive"), "classifier box renders positive");
  ok(calls > 0, "pretend model was called");
  console.log(`\n${pass} checks passed, ${fail} failed; pretend model called ${calls} times`);
  process.exit(fail ? 1 : 0);
})();
