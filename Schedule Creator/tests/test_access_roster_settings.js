async function runAccessRosterSettingsTests(source) {
  document.body.insertAdjacentHTML("beforeend", `
    <section id="rosterSettingsPanel" hidden><p id="rosterSettingsNote"></p>
    <p id="rosterSettingsMessage"></p><div id="rosterSettingsTable"></div></section>`);
  const $ = selector => document.querySelector(selector);
  const record = (id, name) => ({employeeId: id, name, location: "Kingston", role: "Cashier",
    revision: 1, starts: [6, 8.5], settings: {flex: "Yes", reason: "", proximity: 1, preferred: 6}});
  const ann = record("a", "Ann"), bob = record("b", "Bob");
  const cell = (row, value) => { row.insertCell().textContent = value; };
  const requests = [];
  let locked = false;
  const api = (path, method, payload) => method === "PUT"
    ? new Promise((resolve, reject) => requests.push({path, payload, resolve, reject}))
    : path.includes("/my/") ? {employee: ann, locked} : {employees: [ann, bob], locked};
  const markup = source.slice(source.indexOf("let rosterSettingsRecords"), source.indexOf("let metaSettingsRecords"));
  const {openRosterSettings, personal} = new Function("$", "api", "cell", `
    let role="manager", accountRole="manager", personalMode=false;
    ${markup}
    return {openRosterSettings, personal: () => { role="employee"; personalMode=true; }};
  `)($, api, cell);
  const rows = () => [...document.querySelectorAll("#rosterSettingsTable tbody tr")];
  const control = (row, field) => row.querySelector(`[data-roster-field="${field}"]`);
  const save = row => row.querySelector("button");
  let passed = 0;
  const check = (condition, label) => { if (!condition) throw Error(label); passed++; };
  await openRosterSettings();
  check(rows().length === 2 && control(rows()[0], "random").disabled && control(rows()[0], "attendance").disabled,
    "Managers see team rows but cannot edit random or attendance.");
  control(rows()[0], "proximity").value = "2";
  control(rows()[1], "proximity").value = "3";
  save(rows()[0]).click();
  check(control(rows()[0], "proximity").disabled && !control(rows()[1], "proximity").disabled,
    "Only the row being saved stops accepting edits.");
  check(requests[0].path === "/api/access/roster-settings" && requests[0].payload.employeeId === "a"
    && requests[0].payload.changes.proximity === 2, "Manager saves the selected employee's changes.");
  requests[0].resolve({settings: {...ann.settings, proximity: 2}, revision: 2});
  await Promise.resolve();
  check(control(rows()[0], "proximity").value === "2" && control(rows()[1], "proximity").value === "3",
    "Saving one row retains another row's unsaved edit.");
  save(rows()[1]).click();
  requests[1].reject(Error("Settings changed elsewhere."));
  await Promise.resolve();
  check(!control(rows()[1], "proximity").disabled && control(rows()[1], "proximity").value === "3"
    && $("#rosterSettingsMessage").textContent === "Settings changed elsewhere.", "A rejected save keeps the draft and explains the error.");
  personal();
  await openRosterSettings();
  check(rows().length === 1 && [...rows()[0].querySelectorAll("[data-roster-field]:enabled")].map(node => node.dataset.rosterField).join() === "flex,reason,preferred",
    "Linked-manager personal view edits only the three employee fields.");
  control(rows()[0], "preferred").value = "8.5";
  save(rows()[0]).click();
  check(requests[2].path === "/api/access/my/roster-settings" && !("employeeId" in requests[2].payload)
    && requests[2].payload.changes.preferred === 8.5, "Personal save uses the self-service endpoint.");
  requests[2].resolve({settings: {...ann.settings, preferred: 8.5}, revision: 2});
  await Promise.resolve();
  locked = true;
  await openRosterSettings();
  check(!rows()[0].querySelector("[data-roster-field]:enabled") && save(rows()[0]).disabled, "A locked roster is read-only.");
  return {passed};
}
