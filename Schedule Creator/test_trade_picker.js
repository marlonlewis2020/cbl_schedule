async function runTradePickerTests() {
  let checks = 0, submitted = null, completed = false;
  const assert = (condition, message) => { if (!condition) throw Error(message); checks++; };
  const settle = async () => { await Promise.resolve(); await Promise.resolve(); };
  const warnings = {
    a: [{hours: 8, requiredHours: 11, message: "Reduced rest: 8 hours; required 11 hours."}],
    b: [{hours: 9, requiredHours: 11, message: "Reduced rest: 9 hours; required 11 hours."}]
  };
  const choices = {employee1: "a", schedules: [
    {runId: "week-1", locationId: "loc-1", locationName: "Kingston", team: "Cashier",
      start: "2026-11-09", end: "2026-11-15", employees: [{id: "a", name: "Ann"}, {id: "b", name: "Bob"}]}
  ]};
  const api = async (path, method, body) => {
    if (path.endsWith("/choices")) return choices;
    if (path.endsWith("/options")) return {
      days: [{day: 0, date: "2026-11-09", slotA: 6, slotB: null}, {day: 1, date: "2026-11-10", slotA: null, slotB: 14}],
      shiftDuration: 8, combinations: [{days: [0, 1], warnings, shiftCounts: {a: 5, b: 5}}], explanations: ["Both employees require at least 5 shifts."]
    };
    submitted = {path, method, body}; return {id: "trade-1", state: "requested"};
  };
  await TradePicker.open({base: "/api/access/trades", api, onCreated: () => { completed = true; }});
  let dialog = document.querySelector("#workforceTradeDialog");
  const $ = selector => dialog.querySelector(selector);
  assert(dialog.open, "Native modal must be open");
  assert($("[data-team]").options.length === 2, "Location/team choices must come from server");
  $("[data-team]").selectedIndex = 1; $("[data-team]").dispatchEvent(new Event("change"));
  $("[data-week]").value = "0"; $("[data-week]").dispatchEvent(new Event("change"));
  assert($("[data-first]").disabled && $("[data-first]").value === "a", "Employee 1 must be immutable");
  assert($("[data-second]").options.length === 2 && $("[data-second]").options[1].value === "b", "Employee 2 must exclude employee 1");
  $("[data-second]").value = "b"; $("[data-second]").dispatchEvent(new Event("change")); await settle();
  const days = [...$("[data-options]").querySelectorAll("input[type=checkbox]")];
  assert(days.length === 2, "List swap-day checkboxes");
  days[0].click();
  assert($("[data-submit]").disabled, "Invalid single-day combination must not submit");
  days[1].click();
  assert(!$("[data-warnings]").hidden && $("[data-warnings]").textContent.includes("Ann") && $("[data-warnings]").textContent.includes("Bob"), "Warn about both participants");
  assert(!$("[data-ack-label]").hidden && $("[data-submit]").disabled, "Initiator must acknowledge");
  $("[data-ack]").click();
  assert(!$("[data-submit]").disabled, "Acknowledged valid combined trade must submit");
  $("[data-reason]").value = "Balance the period"; $("form").requestSubmit(); await settle();
  assert(submitted.method === "POST" && submitted.body.employeeA === "a" && submitted.body.employeeB === "b", "Submit validated participant IDs");
  assert(JSON.stringify(submitted.body.days) === "[0,1]" && submitted.body.acknowledgeWarnings && submitted.body.warnings === warnings, "Submit combined days and exact acknowledged warnings");
  assert(completed && !document.querySelector("#workforceTradeDialog"), "Successful submission closes modal");
  choices.employee1 = null;
  await TradePicker.open({base: "/api/shift-trades", api});
  dialog = document.querySelector("#workforceTradeDialog");
  $("[data-team]").selectedIndex = 1; $("[data-team]").dispatchEvent(new Event("change"));
  $("[data-week]").value = "0"; $("[data-week]").dispatchEvent(new Event("change"));
  assert(!$("[data-first]").disabled && $("[data-first]").options.length === 3, "Managers/admins select employee 1");
  $("[data-first]").value = "a"; $("[data-first]").dispatchEvent(new Event("change"));
  $("[data-second]").value = "b"; $("[data-second]").dispatchEvent(new Event("change")); await settle();
  $("[data-options] input[value='0']").click(); $("[data-options] input[value='1']").click();
  assert(!$("[data-ack-label]").hidden && $("[data-submit]").disabled && $("[data-warnings]").textContent.includes("must sign in"), "Administrator must review warnings without substituting for employees");
  $("[data-ack]").click();
  assert(!$("[data-submit]").disabled && $("[data-counts]").textContent.includes("5 shifts"), "Reviewed exception shows final counts and can submit");
  const cancel = new Event("cancel", {cancelable: true}); dialog.dispatchEvent(cancel);
  assert(!document.querySelector("#workforceTradeDialog"), "Escape/cancel removes modal");
  await TradePicker.open({base: "/api/shift-trades", api: async () => { throw Error("Access denied"); }});
  dialog = document.querySelector("#workforceTradeDialog");
  assert($("[data-message]").textContent === "Access denied" && $("[data-submit]").disabled, "Show API failures without success fallback");
  $("[data-close]").click();
  return {passed: checks};
}

async function runAdminTradeEntryTest(source) {
  const start = source.indexOf("function openTrades("), end = source.indexOf("\n}", start);
  if (start < 0 || end < 0) throw Error("Administrator trade entry missing");
  let call = null;
  const open = new Function("membershipFeatureEnabled", "directoryRequest", "tenantAuthCsrfToken", "message",
    source.slice(start, end + 2) + ";return openTrades;")(
      () => true, async (path, options) => { call = {path, options}; return {schedules: [], employee1: null}; },
      "fixture-csrf", () => {}
    );
  const url = location.href;
  await open();
  const dialog = document.querySelector("#workforceTradeDialog");
  if (!dialog?.open || location.href !== url) throw Error("Administrator Shift trade must open a popup, not redirect");
  if (call.path !== "/shift-trades/choices" || call.options.headers["X-CSRF-Token"] !== "fixture-csrf") throw Error("Administrator popup must use authenticated server choices");
  dialog.querySelector("[data-close]").click();
  return {passed: 2};
}

function runTradeThemeTests(adminCss, tradeCss) {
  const frame = document.createElement("iframe");
  document.body.append(frame);
  const doc = frame.contentDocument;
  doc.body.innerHTML = '<div class="panel">Panel</div><button>Button</button><dialog class="workforce-trade"><select><option>Employee</option></select><textarea>Reason</textarea><button>Submit</button><div class="trade-warning">Reduced rest</div></dialog>';
  const original = doc.createElement("style"), shared = doc.createElement("style");
  original.textContent = adminCss; doc.head.append(original);
  shared.textContent = tradeCss;
  const styles = element => {
    const computed = frame.contentWindow.getComputedStyle(element);
    return [computed.color, computed.backgroundColor, computed.borderColor];
  };
  let checks = 0;
  try {
    for (const theme of ["light", "dark"]) {
      shared.remove();
      doc.documentElement.dataset.theme = theme;
      const elements = [doc.body, doc.querySelector(".panel"), doc.querySelector("body > button")];
      const before = elements.map(styles);
      doc.head.append(shared);
      if (JSON.stringify(before) !== JSON.stringify(elements.map(styles))) throw Error(`${theme}: shared trade CSS changed the surrounding page`);
      checks++;
      const dialog = doc.querySelector("dialog");
      const surface = theme === "dark" ? "rgb(20, 46, 57)" : "rgb(255, 255, 255)";
      const control = theme === "dark" ? "rgb(25, 57, 69)" : "rgb(255, 255, 255)";
      if (styles(dialog)[1] !== surface) throw Error(`${theme}: wrong popup surface`);
      checks++;
      for (const element of dialog.querySelectorAll("select, textarea")) {
        if (styles(element)[1] !== control || styles(element)[0] !== styles(dialog)[0]) throw Error(`${theme}: unreadable popup control`);
        checks++;
      }

      if (styles(dialog.querySelector(".trade-warning"))[0] === styles(dialog.querySelector(".trade-warning"))[1]) throw Error(`${theme}: unreadable rest warning`);
      checks++;
    }
    return {passed: checks};
  } finally { frame.remove(); }
}

async function runTradeInboxTests(html) {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const source = [...parsed.scripts].find(script => !script.src).textContent;
  const originalFetch = window.fetch, originalConfirm = window.confirm, originalPrompt = window.prompt;
  let checks = 0;
  const assert = (condition, message) => { if (!condition) throw Error(message); checks++; };
  const warnings = {a: [{message: "Approved leave on 2026-11-09."}, {message: "Shift overlap: simultaneous assignments."}]};
  try {
    for (const [role, action, label] of [["employee", "confirm", "Accept trade"], ["manager", "accept", "Manager accept"], ["admin", "approve", "Administrator approve"]]) {
      document.body.innerHTML = parsed.body.innerHTML;
      const trade = {
        id: "fixture", runId: "week", start: "2026-11-09", shiftDuration: 8, days: [0], day: 0,
        employeeA: "a", employeeB: "b", employeeNameA: "Ann", employeeNameB: "Bob",
        swaps: [{day: 0, slotA: 22, slotB: 6}], shiftCounts: {a: 5, b: 6},
        state: action === "confirm" ? "requested" : action === "accept" ? "confirmed" : "manager_accepted",
        constraintPolicy: "warnings-five", warnings, restWarnings: warnings, unread: true,
        initiatorName: role === "employee" ? "Ann" : role === "manager" ? "Michelle" : "Administrator",
        initiatedRole: role,
        restAcknowledged: ["a"], acknowledged: ["a"], version: 1, actions: [action, "reject"], history: [], reason: "Test exception"
      };
      let posted = null, consent = false, displayed = "";
      window.confirm = text => { displayed = text; return consent; };
      window.prompt = () => "Reviewed the exceptions";
      window.fetch = async (path, options = {}) => ({ok: true, json: async () => {
        if (path === "/api/access/state") return {authenticated: role !== "admin", user: {role, employeeId: "b", name: "Bob"}, csrfToken: "fixture"};
        if (path === "/api/tenant-auth/state") return {authenticated: true, csrfToken: "fixture"};
        if (path.endsWith("/action")) { posted = JSON.parse(options.body); return {state: "accepted"}; }
        return {trades: [trade], unread: 1};
      }});
      await new Function(source.replace("start().catch(", "return start().catch("))();
      const card = document.querySelector(".trade-card");
      const summary = card.querySelector(":scope > summary");
      assert(card.tagName === "DETAILS" && !card.open && !card.querySelector(".trade-content").checkVisibility(), `${role}: collapsed by default`);
      assert(summary.textContent.includes("2026") && summary.textContent.includes(`Initiated by ${trade.initiatorName} (${role})`) && summary.textContent.includes("Awaiting") && summary.textContent.includes("Unread update"), `${role}: week, actual initiator, status and unread summary`);
      summary.click();
      assert(card.open && !posted && card.querySelector(".trade-content").checkVisibility(), `${role}: expansion does not submit consent`);
      assert(card.textContent.includes("Ann") && card.textContent.includes("Bob") && card.textContent.includes("22:00 – 06:00 (+1 day)"), `${role}: named readable overnight shift`);
      assert(card.textContent.includes("Ann: 5") && card.textContent.includes("Bob: 6"), `${role}: resulting weekly counts`);
      const button = [...card.querySelectorAll("button")].find(button => button.textContent === label);
      await button.onclick();
      assert(!posted && displayed.includes("Approved leave") && displayed.includes("Shift overlap"), `${role}: cancelled warning consent does not submit`);
      consent = true;
      await button.onclick();
      assert(posted.action === action && posted.acknowledgeWarnings && JSON.stringify(posted.warnings) === JSON.stringify(warnings), `${role}: all warnings accompany acceptance`);
      posted = null; displayed = ""; consent = false;
      const reloaded = document.querySelector(".trade-card");reloaded.open = true;
      await [...reloaded.querySelectorAll("button")].find(button => button.textContent === "Reject trade").onclick();
      assert(posted.action === "reject" && !posted.acknowledgeWarnings && !displayed, `${role}: rejection does not require exception consent`);
    }
    const previous = document.documentElement.dataset.theme;
    document.querySelector("#theme").click();
    assert(document.documentElement.dataset.theme !== previous, "Inbox theme toggle");
    return {passed: checks};
  } finally {
    window.fetch = originalFetch; window.confirm = originalConfirm; window.prompt = originalPrompt;
  }
}
