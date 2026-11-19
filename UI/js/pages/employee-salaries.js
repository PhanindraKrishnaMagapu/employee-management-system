// Per-employee salary history. Amounts stay in page memory only.

let employeeSalariesUser = null;
let employeeSalariesEmployeeId = null;
let employeeSalaryRows = [];

function salaryValueOrDash(value) {
  return value === null || value === undefined || value === ""
    ? "-"
    : String(value);
}

function salaryEmployeeName(employee) {
  if (!employee) {
    return "-";
  }
  const name = [employee.first_name, employee.last_name]
    .filter(function (part) {
      return part !== null && part !== undefined && String(part).trim() !== "";
    })
    .join(" ");
  return name || employee.employee_code || ("Employee #" + employee.id);
}

function formatSalaryAmount(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "-";
  }
  return amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function salaryStatus(salary) {
  const today = new Date().toISOString().slice(0, 10);
  if (salary.effective_from > today) {
    return "Scheduled";
  }
  if (!salary.effective_to || salary.effective_to >= today) {
    return "Current";
  }
  return "Historical";
}

function renderEmployeeSalarySummary(employee) {
  const rows = [
    ["Employee", salaryEmployeeName(employee)],
    ["Employee code", employee.employee_code],
    ["Official email", employee.official_email],
    ["Status", employee.employment_status],
    ["Department", "Department #" + employee.department_id],
    ["Designation", "Designation #" + employee.designation_id],
  ];

  document.getElementById("employee-summary").innerHTML = rows
    .map(function (row) {
      return (
        "<div>" +
        '<span class="label">' + escapeHtml(row[0]) + "</span>" +
        escapeHtml(salaryValueOrDash(row[1])) +
        "</div>"
      );
    })
    .join("");
}

function renderEmployeeSalaryRows() {
  document.getElementById("salary-rows").innerHTML = employeeSalaryRows
    .map(function (salary) {
      const id = Number(salary.id);
      const edit = canManageSalary(employeeSalariesUser)
        ? '<a class="link" href="/pages/salary-form.html?id=' + id + '">Edit</a>'
        : "";

      return (
        "<tr>" +
        "<td>" + escapeHtml(formatSalaryAmount(salary.annual_salary)) + "</td>" +
        "<td>" + escapeHtml(salary.currency) + "</td>" +
        "<td>" + escapeHtml(salaryValueOrDash(salary.effective_from)) + "</td>" +
        "<td>" + escapeHtml(salaryValueOrDash(salary.effective_to)) + "</td>" +
        '<td><span class="badge">' + escapeHtml(salaryStatus(salary)) + "</span></td>" +
        '<td class="actions-cell">' + edit + "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("salary-empty").hidden = employeeSalaryRows.length !== 0;
}

async function findEmployeeSummary() {
  const result = await apiGet("/api/salaries/employees");
  if (!handleApiResult(result)) {
    return null;
  }
  const employees = Array.isArray(result.data.employees)
    ? result.data.employees
    : [];
  return employees.find(function (employee) {
    return Number(employee.id) === employeeSalariesEmployeeId;
  }) || null;
}

async function loadEmployeeSalaries() {
  const result = await apiGet(
    "/api/salaries?employee_id=" + employeeSalariesEmployeeId +
      "&limit=500&offset=0"
  );
  if (!handleApiResult(result)) {
    return;
  }

  employeeSalaryRows = Array.isArray(result.data.salaries)
    ? result.data.salaries
    : [];

  let employee = employeeSalaryRows.length
    ? employeeSalaryRows[0].employee
    : await findEmployeeSummary();

  if (!employee) {
    showMessage("error", "Employee salary history is unavailable.");
    return;
  }

  renderEmployeeSalarySummary(employee);
  renderEmployeeSalaryRows();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  employeeSalariesUser = user;
  initShell(user, "salaries");
  showFlash();

  if (!canReadSalary(user)) {
    showMessage("error", "Your role does not grant access to salary records.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  employeeSalariesEmployeeId = Number(params.get("employee_id"));
  if (!Number.isInteger(employeeSalariesEmployeeId) || employeeSalariesEmployeeId <= 0) {
    showMessage("error", "No employee was selected.");
    return;
  }

  const addLink = document.getElementById("add-salary-link");
  if (canManageSalary(user)) {
    addLink.href =
      "/pages/salary-form.html?employee_id=" + employeeSalariesEmployeeId;
  } else {
    addLink.hidden = true;
  }

  await loadEmployeeSalaries();
})();
