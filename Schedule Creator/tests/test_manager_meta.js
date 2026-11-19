async function runManagerMetaTests(source) {
  const fixture = document.createElement("section");
  fixture.innerHTML = `
    <button id="openMetaSettings"></button><section id="metaSettingsPanel">
    <p id="metaSettingsNote"></p><p id="metaSettingsMessage"></p>
    <div id="metaSettingsTable"></div></section>`;
  document.body.append(fixture);
  const $ = selector => fixture.querySelector(selector);
  const rows = () => [...$("#metaSettingsTable").querySelectorAll("tbody tr")];
  const location = name => ({name, intensity: Array(7).fill(0.25), open: Array(7).fill(1)});
  const requests = [];
  let locked = false;
  const api = (path, method, payload) => {
    if (!method) return {locations: [location("Kingston"), location("St Ann")], revision: 10, locked};
    return new Promise((resolve, reject) => requests.push({path, payload, resolve, reject}));
  };
  const start = source.indexOf("let metaSettingsRecords");
  const end = source.indexOf("function clockLabel", start);
  const open = new Function("$", "api", `${source.slice(start, end)}; return openMetaSettings;`)($, api);
  let passed = 0;
  const check = (condition, message) => { if (!condition) throw Error(message); passed++; };
  const edit = (input, value) => {
    if (input.type === "checkbox") input.checked = value;
    else input.value = value;
    input.dispatchEvent(new Event("change"));
  };
  try {
    await open();
    const [kingston, stAnn] = rows();
    const intensity = row => row.querySelector('[data-meta-field="intensity"]');
    const operating = row => row.querySelector('[data-meta-field="open"]');
    const save = row => row.querySelector("button");
    edit(intensity(kingston), "40");
    edit(operating(stAnn), false);
    save(kingston).click();
    check(requests[0].path === "/api/access/meta-settings" && requests[0].payload.revision === 10
      && requests[0].payload.changes[0].value === 0.4, "Kingston sends the edited percentage and current revision.");
    check(save(stAnn).disabled, "Another save must wait for the shared revision.");
    const saved = location("Kingston");
    saved.intensity[0] = 0.4;
    requests[0].resolve({location: saved, revision: 11});
    await Promise.resolve();
    await Promise.resolve();
    check(save(rows()[0]).disabled && intensity(rows()[0]).value === "40", "Saved row keeps the persisted value.");
    check(!operating(rows()[1]).checked && !save(rows()[1]).disabled, "Saving Kingston must preserve the unsaved St Ann change.");
    save(rows()[1]).click();
    check(requests[1].payload.revision === 11 && requests[1].payload.location === "St Ann"
      && requests[1].payload.changes[0].value === 0, "St Ann saves with the new shared revision.");
    requests[1].reject(new Error("Settings changed. Reload and retry."));
    await Promise.resolve();
    await Promise.resolve();
    check($("#metaSettingsMessage").textContent === "Settings changed. Reload and retry." && !save(rows()[1]).disabled
      && !operating(rows()[1]).checked, "A rejected save shows the error and retains the edit.");
    locked = true;
    await open();
    check(rows().every(row => [...row.querySelectorAll("input, button")].every(control => control.disabled)),
      "Locked META disables all edits and saves.");
    return {passed};
  } finally {
    fixture.remove();
  }
}
