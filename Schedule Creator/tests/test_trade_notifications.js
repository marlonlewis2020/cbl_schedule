async function runTradeNotificationTests(source) {
  new Function(source);
  const section = source.slice(source.indexOf("let attendanceNotifications="), source.indexOf("function blankRosterProfile("));
  const original = document.body.innerHTML;
  let checks = 0, enabled = true, error = false, feedback = "", requests = [], feedbackToasts = [], archivedAll = false, pollClock = Date.parse("2026-11-14T12:00:00Z"), attendanceEvents = [{id: "late", read: false, date: "2026-11-09", message: "Late employee", createdAt: "2026-11-14T11:59:00Z"}];
  const assert = (value, message) => { if (!value) throw Error(message); checks++; };
  const originalDateNow = Date.now;
  Date.now = () => pollClock;
  const trade = {id: "fixture", state: "manager_accepted", actions: ["approve"], unread: true, version: 3, createdAt: "2026-11-14T11:59:00Z", updatedAt: "2026-11-14T11:59:00Z", start: "2026-11-09", employeeNameA: "Ann", employeeNameB: "Bob"};
  try {
    document.body.innerHTML = '<button id="notificationButton"><span id="notificationBadge"></span></button><div id="notificationPanel"></div>';
    const api = async (path, options) => {
      requests.push({path, options});
      if (error) throw Error("Refresh failed");
      if (path === "/attendance/notifications/archive-all") { archivedAll = true; return {archived: 1}; }
      if (path.endsWith("/read")) { trade.unread = false; return {updated: true}; }
      if (path === "/shift-trades") return {trades: [trade, {...trade, id: "other", state: "approved", actions: ["apply"]}]};
      return {notifications: archivedAll ? [] : attendanceEvents};
    };
    const functions = new Function("$", "esc", "timeLabel", "directoryRequest", "membershipFeatureEnabled", "tenantAuthCsrfToken", "message", "addFeedback",
      section + ";return {pollAttendanceNotifications,openTradeApproval,archiveAllAttendanceNotifications};")(
      id => document.getElementById(id), value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;"),
      String, api, () => enabled, "fixture-token", text => { feedback = text; }, text => feedbackToasts.push(text)
    );
    await functions.pollAttendanceNotifications();
    assert(feedbackToasts.length === 0, "Initial polling does not replay existing alerts as toasts");
    assert(document.getElementById("notificationBadge").textContent === "2", "Bell counts attendance and pending trade unread updates");
    assert(document.querySelector('[data-action="archiveAllNotifications"]')?.textContent === "Clear all attendance", "Active alert panel offers Clear all attendance");
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
    assert(feedbackToasts.length === 0, "Pre-existing trade updates remain silent during baseline polling");
    dialog.close();
    dialog.dispatchEvent(new Event("close"));
    assert(frame.getAttribute("src") === "about:blank", "Closing unloads protected inbox and refreshes notifications");
    document.body.insertAdjacentHTML("beforeend", '<div id="notificationPanel"></div>');
    await functions.archiveAllAttendanceNotifications();
    assert(requests.some(item => item.path === "/attendance/notifications/archive-all"), "Clear all archives attendance through its dedicated endpoint");
    assert(!document.getElementById("notificationPanel").textContent.includes("Late employee"), "Archived attendance alerts disappear after refresh");
    assert(document.querySelectorAll('[data-action="openTradeApproval"]').length === 1, "Clearing attendance leaves pending trade approvals visible");
    trade.state = "approved";
    await functions.pollAttendanceNotifications();
    assert(!document.querySelector('[data-action="openTradeApproval"]'), "Resolved approval disappears on refresh");
    enabled = false; requests = [];
    await functions.pollAttendanceNotifications();
    assert(!requests.some(item => item.path === "/shift-trades"), "Unavailable trade entitlement does not poll trade API");
    archivedAll = false;
    pollClock += 1000;
    attendanceEvents = [
      ...attendanceEvents,
      {id: "new-late", read: false, date: "2026-11-10", message: "Another late employee", createdAt: new Date(pollClock - 100).toISOString().replace("T", " ").replace("Z", "")},
      {id: "missing-time", read: false, date: "2026-11-10", message: "Missing timestamp", createdAt: "not-a-date"}
    ];
    await functions.pollAttendanceNotifications();
    assert(feedbackToasts.length === 1 && feedbackToasts[0] === "Another late employee", "New attendance alert is toasted once");
    assert(!feedbackToasts.includes("Missing timestamp"), "Invalid event timestamps fail closed without a toast");
    pollClock += 1000;
    attendanceEvents.push({id: "older-page", read: false, date: "2026-11-09", message: "Older paginated alert", createdAt: "2026-11-14T11:59:59Z"});
    await functions.pollAttendanceNotifications();
    assert(feedbackToasts.length === 1, "Older paginated alerts and repeated polls do not toast");
    trade.state = "manager_accepted";trade.version=4;trade.updatedAt=new Date(pollClock + 100).toISOString();
    enabled = true;pollClock += 200;
    await functions.pollAttendanceNotifications();
    assert(feedbackToasts.length === 2&&feedbackToasts[1].includes("Shift trade pending administrator approval"), "A newly updated trade version with a fresh timestamp toasts once");
    await functions.pollAttendanceNotifications();
    assert(feedbackToasts.length === 2, "Repeated polling does not duplicate trade update toasts");
    error = true;
    await functions.pollAttendanceNotifications();
    assert(feedback.includes("Refresh failed"), "Polling errors are surfaced");
    return {passed: checks};
  } finally {
    Date.now = originalDateNow;
    document.getElementById("tradeApprovalDialog")?.remove();
    document.body.innerHTML = original;
  }
}
