/* Shared authenticated trade picker for administrator and workforce portals. */
window.TradePicker = {
  rememberTheme(theme) {
    try { localStorage.setItem("cbl-trade-theme", theme); }
    catch (error) { console.warn("Unable to remember trade theme.", error); }
  },
  restoreTheme() {
    try { return localStorage.getItem("cbl-trade-theme") === "dark" ? "dark" : "light"; }
    catch (error) { console.warn("Unable to restore trade theme.", error); return "light"; }
  },
  shift(start, duration = 0) {
    if (start === null) return "Day off";
    const clock = value => `${String(Math.floor(value % 24)).padStart(2, "0")}:${String(Math.round(value % 1 * 60)).padStart(2, "0")}`;
    return duration ? `${clock(start)} – ${clock(start + duration)}${start + duration >= 24 ? " (+1 day)" : ""}` : clock(start);
  },
  warnings(container, warnings, names) {
    container.replaceChildren();
    for (const [person, entries] of Object.entries(warnings)) {
      const section = document.createElement("section"), heading = document.createElement("h3"), list = document.createElement("ul");
      heading.textContent = names[person] || person;
      for (const entry of entries) { const li = document.createElement("li"); li.textContent = entry.message; list.append(li); }
      section.append(heading, list); container.append(section);
    }
  },
  async open({api, base, onCreated = () => {}}) {
    if (document.documentElement.dataset.theme) TradePicker.rememberTheme(document.documentElement.dataset.theme);
    if (document.querySelector("#workforceTradeDialog")) return;
    const dialog = document.createElement("dialog");
    dialog.id = "workforceTradeDialog";
    dialog.className = "workforce-trade";
    dialog.setAttribute("aria-labelledby", "workforceTradeTitle");
    dialog.innerHTML = `<form>
      <header><h2 id="workforceTradeTitle">Shift trade</h2><button type="button" data-close aria-label="Close shift trade">Close</button></header>
      <p class="trade-intro">Choose your team, period and employees. Review each person's before → after shifts, then select the days to swap.</p>
      <p class="trade-rule">Both employees must finish this week with <strong>at least 5 shifts</strong>. Other scheduling violations require explicit employee, manager and administrator acknowledgement.</p>
      <div class="trade-fields">
        <label>Location × team<select data-team required><option value="">Loading teams…</option></select></label>
        <label>Week / period<select data-week required disabled></select></label>
        <label>Employee 1 · offering<select data-first required disabled></select></label>
        <label>Employee 2 · receiving<select data-second required disabled></select></label>
      </div>
      <fieldset data-options disabled><legend>Eligible swap days</legend><p>Select both employees first.</p></fieldset>
      <p data-counts class="trade-rule" hidden></p>
      <div data-warnings class="trade-warning" hidden></div>
      <label data-ack-label hidden><input data-ack type="checkbox"> I have reviewed all scheduling warnings for both employees and accept these exceptions. This does not replace anyone else's consent.</label>
      <label>Trade reason<textarea data-reason required maxlength="500" rows="3"></textarea></label>
      <p data-message class="error" role="alert" aria-live="polite"></p>
      <footer><a href="${base.startsWith("/api/access") ? "/trades" + (location.search.includes("view=employee") ? "?view=employee" : "") : "/trades"}">Open approvals inbox</a><button data-submit type="submit" disabled>Submit trade</button></footer>
    </form>`;
    document.body.append(dialog);
    dialog.showModal();
    const $ = selector => dialog.querySelector(selector);
    let schedules = [], fixedEmployee = null, fixedLocation = null, selectedSchedule = null, options = null, revision = 0;
    const close = () => { revision++; dialog.close(); dialog.remove(); };
    $("[data-close]").onclick = close;
    dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
    const fill = (select, items, placeholder) => {
      select.replaceChildren(new Option(placeholder, ""));
      items.forEach(item => select.add(new Option(item.label, item.value)));
      select.disabled = !items.length;
    };
    const selected = () => [...$("[data-options]").querySelectorAll("input:checked")].map(input => Number(input.value)).sort((a, b) => a - b);
    const combination = () => options?.combinations.find(option => JSON.stringify(option.days) === JSON.stringify(selected()));
    const clearOptions = () => {
      revision++;
      options = null;
      $("[data-options]").replaceChildren(Object.assign(document.createElement("legend"), {textContent: "Eligible swap days"}));
      $("[data-options]").disabled = true;
      $("[data-warnings]").hidden = true;
      $("[data-counts]").hidden = true;
      $("[data-ack-label]").hidden = true;
      $("[data-ack]").checked = false;
      $("[data-submit]").disabled = true;
      $("[data-message]").textContent = "";
    };
    const evaluate = () => {
      const option = combination(), warnings = option?.warnings || option?.restWarnings || {};
      const names = Object.fromEntries(selectedSchedule.employees.map(employee => [employee.id, employee.name]));
      TradePicker.warnings($("[data-warnings]"), warnings, names);
      if (Object.keys(warnings).length) {
        const p = document.createElement("p");
        p.textContent = "Both employees must sign in and acknowledge these warnings. The manager and administrator must also review and acknowledge before approval.";
        $("[data-warnings]").append(p);
      }
      $("[data-warnings]").hidden = !Object.keys(warnings).length;
      $("[data-ack-label]").hidden = !Object.keys(warnings).length;
      $("[data-counts]").hidden = !option?.shiftCounts;
      $("[data-counts]").textContent = option?.shiftCounts ? "After trade: " + Object.entries(option.shiftCounts).map(([id, count]) => `${names[id] || id}: ${count} shifts`).join(" · ") : "";
      $("[data-submit]").disabled = !option || (Object.keys(warnings).length > 0 && !$("[data-ack]").checked);
      $("[data-submit]").textContent = Object.keys(warnings).length ? "Submit with acknowledged exceptions" : "Submit trade";
      $("[data-message]").textContent = selected().length && !option ? "This combined selection would leave an employee below 5 shifts, or no longer matches the available options. Choose a valid combined selection." : "";
    };
    $("[data-ack]").onchange = evaluate;
    const loadOptions = async () => {
      clearOptions();
      const employeeA = $("[data-first]").value, employeeB = $("[data-second]").value;
      if (!selectedSchedule || !employeeA || !employeeB) return;
      const ticket = revision;
      $("[data-message]").textContent = "Checking combined swaps…";
      try {
        const result = await api(`${base}/options`, "POST", {runId: selectedSchedule.runId, employeeA, employeeB, locationId: selectedSchedule.locationId});
        if (ticket !== revision || !dialog.isConnected) return;
        options = result;
        $("[data-options]").disabled = false;
        result.days.forEach(day => {
          const label = document.createElement("label"), input = document.createElement("input");
          label.className = "trade-day";
          input.type = "checkbox"; input.value = day.day;
          input.onchange = () => { $("[data-ack]").checked = false; evaluate(); };
          const body = document.createElement("span"), date = document.createElement("strong");
          date.textContent = day.date; body.append(date);
          for (const [id, before, after] of [[employeeA, day.slotA, day.slotB], [employeeB, day.slotB, day.slotA]]) {
            const line = document.createElement("span");
            line.textContent = `${selectedSchedule.employees.find(e => e.id === id)?.name || id}: ${TradePicker.shift(before, result.shiftDuration)} → ${TradePicker.shift(after, result.shiftDuration)}`;
            body.append(line);
          }
          label.append(input, body);
          $("[data-options]").append(label);
        });
        if (result.combinations.length) {
          const details = document.createElement("details"), summary = document.createElement("summary"), p = document.createElement("p");
          summary.textContent = "Valid combined selections";
          p.textContent = result.combinations.map(item => item.days.map(day => result.days.find(item => item.day === day).date).join(" + ")).join("; ");
          details.append(summary, p); $("[data-options]").append(details);
        }
        $("[data-message]").textContent = result.days.length ? "Select swap days to review the combined result." : "No eligible swaps. " + result.explanations.join(" ");
      } catch (error) {
        if (ticket === revision && dialog.isConnected) $("[data-message]").textContent = error.message;
      }
    };
    $("[data-first]").onchange = () => {
      clearOptions();
      fill($("[data-second]"), selectedSchedule.employees.filter(employee => employee.id !== $("[data-first]").value).map(employee => ({label: `${employee.name} (${employee.id})`, value: employee.id})), "Choose employee 2");
    };
    $("[data-second]").onchange = loadOptions;
    $("[data-week]").onchange = () => {
      clearOptions();
      selectedSchedule = schedules[Number($("[data-week]").value)] || null;
      if ($("[data-week]").value === "") selectedSchedule = null;
      fill($("[data-first]"), (selectedSchedule?.employees || []).filter(employee => !fixedEmployee || employee.id === fixedEmployee).map(employee => ({label: `${employee.name} (${employee.id})`, value: employee.id})), "Choose employee 1");
      fill($("[data-second]"), [], "Choose employee 2");
      if (fixedEmployee && selectedSchedule) {
        $("[data-first]").value = fixedEmployee;
        $("[data-first]").disabled = true;
        $("[data-first]").onchange();
      }
    };
    $("[data-team]").onchange = () => {
      clearOptions(); selectedSchedule = null;
      fill($("[data-week]"), schedules.map((schedule, index) => ({schedule, index})).filter(({schedule}) => JSON.stringify([schedule.locationId, schedule.team]) === $("[data-team]").value).map(({schedule, index}) => ({label: `${schedule.start} to ${schedule.end} · ${schedule.runId}`, value: String(index)})), "Choose week / period");
      fill($("[data-first]"), [], "Choose employee 1"); fill($("[data-second]"), [], "Choose employee 2");
    };
    $("form").onsubmit = async event => {
      event.preventDefault();
      const option = combination();
      if (!option) { $("[data-message]").textContent = "Select an eligible combination first."; return; }
      $("[data-submit]").disabled = true;
      try {
        const result = await api(base, "POST", {runId: selectedSchedule.runId, employeeA: $("[data-first]").value,
          employeeB: $("[data-second]").value, locationId: selectedSchedule.locationId, days: option.days, reason: $("[data-reason]").value,
          warnings: option.warnings || option.restWarnings, acknowledgeWarnings: $("[data-ack]").checked});
        close(); await onCreated(result);
      } catch (error) {
        if (dialog.isConnected) { evaluate(); $("[data-message]").textContent = error.message; }
      }
    };
    try {
      const result = await api(`${base}/choices`);
      if (!dialog.isConnected) return;
      schedules = result.schedules; fixedEmployee = result.employee1; fixedLocation = result.lockedLocation;
      if (base.startsWith("/api/access") && fixedEmployee) $("footer a").href = "/trades?view=employee";
      const teams = new Map(schedules.map(schedule => [JSON.stringify([schedule.locationId, schedule.team]), `${schedule.locationName} × ${schedule.team}`]));
      fill($("[data-team]"), [...teams].map(([value, label]) => ({value, label})), "Choose location × team");
      if (fixedLocation) {
        const value = JSON.stringify([fixedLocation.id, fixedLocation.role]);
        if (teams.has(value)) {
          $("[data-team]").value = value;
          $("[data-team]").onchange();
        }
        $("[data-team]").disabled = true;
        $(".trade-intro").textContent = `Your location is fixed to ${fixedLocation.name} × ${fixedLocation.role}. Choose the period and receiving employee.`;
      }
      if (!schedules.length) $("[data-message]").textContent = "No visible accepted schedules with eligible team assignments.";
    } catch (error) { if (dialog.isConnected) $("[data-message]").textContent = error.message; }
  }
};
