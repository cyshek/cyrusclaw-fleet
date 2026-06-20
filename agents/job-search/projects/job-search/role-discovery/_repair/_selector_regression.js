// Simulate the BUGGY behavior vs the FIXED behavior.
const buggyId = "question_36310349002[]";
function buggySelector(id){ return `[id^=react-select-${id}-option]`; }
function fixedSelector(id){
  const esc = (typeof CSS !== "undefined" && CSS.escape) ? CSS.escape(id) : id.replace(/([\[\]\.\:\(\)\#])/g, "\\$1");
  return `[id^="react-select-${esc}-option"]`;
}
// We can't run document.querySelectorAll without a DOM; instead validate that
// the FIXED selector string is acceptable to a CSS parser. Use the DOMParser
// shim via "linkedom" isn't available; fall back to constructing a Document
// from xmldom isn't quite right either. Use the trick of feeding to a regex
// or to a small lexer. Simpler: use Node's vm + jsdom if available.
try {
  const { JSDOM } = require("jsdom");
  const dom = new JSDOM("<!doctype html><html><body><div id='react-select-question_36310349002[]-option-0'>Decline</div></body></html>");
  const doc = dom.window.document;
  // Buggy: should throw.
  let buggyThrew = false;
  try { doc.querySelectorAll(buggySelector(buggyId)); } catch (e) { buggyThrew = true; }
  // Fixed: should match the option div.
  let fixedHits = doc.querySelectorAll(fixedSelector(buggyId)).length;
  console.log(JSON.stringify({ buggyThrew, fixedHits, buggySel: buggySelector(buggyId), fixedSel: fixedSelector(buggyId) }, null, 2));
  if (!buggyThrew) { console.error("REGRESSION TEST FAIL: buggy selector did not throw"); process.exit(2); }
  if (fixedHits !== 1) { console.error("REGRESSION TEST FAIL: fixed selector matched", fixedHits, "expected 1"); process.exit(3); }
  console.log("REGRESSION TEST PASS");
} catch (e) {
  if (e.code === "MODULE_NOT_FOUND") {
    console.log("jsdom not installed — skipping DOM check; printing selectors:");
    console.log("buggy: " + buggySelector(buggyId));
    console.log("fixed: " + fixedSelector(buggyId));
  } else throw e;
}
