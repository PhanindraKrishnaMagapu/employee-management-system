// Dashboard: employee counts scoped to the signed-in user.

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "dashboard");
  showFlash();

  const viewLink = document.getElementById("view-link");
  const addLink = document.getElementById("add-link");

  if (!canRead(user)) {
    document.getElementById("access-level").textContent = "No employee access";
    viewLink.hidden = true;
    addLink.hidden = true;
    showMessage("error", "Your role does not grant access to employee records.");
    return;
  }

  document.getElementById("access-level").textContent = can(user, "readAll")
    ? "All employees"
    : "Assigned scope";

  if (!canCreate(user)) {
    addLink.hidden = true;
  }

  const result = await apiGet("/api/employees");
  if (!handleApiResult(result)) {
    return;
  }

  const employees = result.data.employees || [];
  document.getElementById("total-employees").textContent = String(employees.length);
  document.getElementById("active-employees").textContent = String(
    employees.filter(function (employee) {
      return employee.employment_status === "Active";
    }).length
  );
})();
