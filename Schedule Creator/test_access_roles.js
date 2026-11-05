async function runAccessRoleTests(source) {
  new Function(source);
  const functionSource = source.slice(source.indexOf("function openAccessRoleDialog("), source.indexOf("let attendanceNotifications="));
  let checks = 0, posted = null, confirmed = false, failed = false, refreshed = 0;
  const assert = (condition, text) => { if (!condition) throw Error(text); checks++; };
  const accounts = [
    {id: "employee", role: "employee", displayName: "Ann", employeeId: "a", email: null, authVersion: 2},
    {id: "manager", role: "manager", displayName: "Manager", employeeId: null, email: "mgr@example.test", authVersion: 3}
  ];
  const employees = [{id: "a", name: "Ann", active: true}, {id: "b", name: "Bob", active: true}, {id: "inactive", name: "Inactive", active: false}];
  const open = new Function("$", "esc", "accessAccounts", "employeeDirectory", "directoryRequest", "tenantAuthCsrfToken", "loadAccessAccounts", "message", "confirm",
    "let accessTemporaryPassword=null;" + functionSource + ";return openAccessRoleDialog;")(
    id => document.getElementById(id),
    value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;"),
    accounts, employees,
    async (path, options) => { posted = {path, ...JSON.parse(options.body), token: options.headers["X-CSRF-Token"]}; if (failed) throw Error("Account conflict"); return {updated: true}; },
    "fixture-token", async () => { refreshed++; }, () => {}, () => confirmed
  );
  try {
    open("employee");
    let dialog = document.getElementById("accessRoleDialog");
    assert(dialog.open && document.getElementById("accessNewRole").value === "manager", "Promotion dialog opens with opposite role");
    assert(document.getElementById("accessRoleEmployee").value === "a" && !dialog.textContent.includes("Inactive"), "Linked employee retained; inactive choices excluded");
    assert(document.getElementById("accessRoleEmail").required && !document.getElementById("accessRoleEmployee").required, "Manager requires email, personal link optional");
    document.getElementById("accessRoleEmail").value = "manager@example.test";
    const submit = () => document.getElementById("accessRoleForm").onsubmit({preventDefault() {}, currentTarget: document.getElementById("accessRoleForm")});
    await submit();
    assert(!posted && dialog.open, "Cancelled confirmation does not submit");
    confirmed = true; failed = true;
    await submit();
    assert(dialog.open && document.getElementById("accessRoleError").textContent === "Account conflict", "Server failure displayed without closing");
    assert(!dialog.querySelector("[type=submit]").disabled, "Failed submission can be corrected");
    failed = false;
    await submit();
    assert(!dialog.open && refreshed === 1 && posted.role === "manager" && posted.employeeId === "a" && posted.authVersion === 2 && posted.token === "fixture-token", "Promotion sends preserved link, concurrency version and CSRF");
    open("manager");
    assert(document.getElementById("accessNewRole").value === "employee" && document.getElementById("accessRoleEmployee").required && !document.getElementById("accessRoleEmail").required, "Demotion requires an employee link");
    document.getElementById("accessRoleEmployee").value = "b";
    await submit();
    assert(posted.role === "employee" && posted.previousRole === "manager" && posted.employeeId === "b" && refreshed === 2, "Demotion saves selected employee and refreshes");
    open("employee");
    const previousPosted = posted;
    dialog.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", cancelable: true}));
    assert(!dialog.open && posted === previousPosted, "Escape closes dialog without submission");
    return {passed: checks};
  } finally { document.getElementById("accessRoleDialog")?.remove(); }
}
