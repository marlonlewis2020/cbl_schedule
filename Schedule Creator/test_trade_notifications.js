async function runTradeNotificationTests(source) {
  new Function(source);
  const section = source.slice(source.indexOf("let attendanceNotifications="), source.indexOf("function blankRosterProfile("));
  const original = document.body.innerHTML;
  let checks = 0, enabled = true, error = false, feedback = "", requests = [];
  const assert = (value, message) => { if (!value) throw Error(message); checks++; };
  const trade = {id: "fixture", state: "manager_accepted", actions: ["approve"], unread: true, version: 3, start: "2026-11-09", employeeNameA: "Ann", employeeNameB: "Bob"};
  try {
    document.body.innerHTML = '<button id="notificationButton"><span id="notificationBadge"></span></button><div id="notificationPanel"></div>';
    const api = async (path, options) => {
      requests.push({path, options});
      if (error) throw Error("Refresh failed");
      if (path.endsWith("/read")) { trade.unread = false; return {updated: true}; }
      if (path === "/shift-trades") return {trades: [trade, {...trade, id: "other", state: "approved", actions: ["apply"]}]};
      return {notifications: [{id: "late", read: false, date: "2026-11-09", message: "Late employee"}]};
    };
    const functions = new Function("$", "esc", "timeLabel", "directoryRequest", "membershipFeatureEnabled", "tenantAuthCsrfToken", "message",
      section + ";return {pollAttendanceNotifications,openTradeApproval};")(
      id => document.getElementById(id), value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;"),
      String, api, () => enabled, "fixture-token", text => { feedback = text; }
    );
    await functions.pollAttendanceNotifications();
    assert(document.getElementById("notificationBadge").textContent === "2", "Bell counts attendance and pending trade unread updates");
    assert(document.querySelectorAll('[data-action="openTradeApproval"]').length === 1, "Only manager-accepted requests show as pending approvals");
    assert(document.getElementById("notificationPanel").textContent.includes("Ann") && document.getElementById("notificationPanel").textContent.includes("administrator approval"), "Notification identifies the pending swap");
    await functions.openTradeApproval("fixture");
    const dialog = document.getElementById("tradeApprovalDialog"), frame = dialog.querySelector("iframe");
    assert(dialog.open && frame.getAttribute("src").includes("/trades?adminView=1&trade=fixture"), "Click opens selected request in an admin-site window");
    assert(frame.title === "Administrator shift trade inbox", "Embedded inbox has accessible title");
    const read = requests.find(item => item.path.endsWith("/read"));
    assert(JSON.parse(read.options.body).version === 3 && read.options.headers["X-CSRF-Token"] === "fixture-token", "Viewing marks only the exact update read with CSRF");
    assert(!requests.some(item => item.path.endsWith("/action")), "Viewing does not approve or acknowledge warnings");
    assert(document.getElementById("notificationBadge").textContent === "1", "Read trade leaves attendance unread count");
    dialog.close();
    dialog.dispatchEvent(new Event("close"));
    assert(frame.getAttribute("src") === "about:blank", "Closing unloads protected inbox and refreshes notifications");
    document.body.insertAdjacentHTML("beforeend", '<div id="notificationPanel"></div>');
    trade.state = "approved";
    await functions.pollAttendanceNotifications();
    assert(!document.querySelector('[data-action="openTradeApproval"]'), "Resolved approval disappears on refresh");
    enabled = false; requests = [];
    await functions.pollAttendanceNotifications();
    assert(!requests.some(item => item.path === "/shift-trades"), "Unavailable trade entitlement does not poll trade API");
    error = true;
    await functions.pollAttendanceNotifications();
    assert(feedback.includes("Refresh failed"), "Polling errors are surfaced");
    return {passed: checks};
  } finally {
    document.getElementById("tradeApprovalDialog")?.remove();
    document.body.innerHTML = original;
  }
}
