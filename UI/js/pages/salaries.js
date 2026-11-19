// Salary records: search, filters, pagination, and edit links.

const SALARY_PAGE_SIZE = 50;

let salaryPageUser = null;
let salaryRows = [];
let salaryTotal = 0;
let salaryOffset = 0;
let salarySearchTimer = null;

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

function salaryQuery() {
  const params = new URLSearchParams();
  params.set("limit", String(SALARY_PAGE_SIZE));
  params.set("offset", String(salaryOffset));

  const search = document.getElementById("search").value.trim();
  if (search) {
    params.set("search", search);
  }

  const employeeId = document.getElementById("employee-filter").value;
  if (employeeId) {
    params.set("employee_id", employeeId);
  }

  const currency = document.getElementById("currency-filter").value.trim();
  if (currency) {
    params.set("currency", currency.toUpperCase());
  }

  const activeOn = document.getElementById("active-on").value;
  if (activeOn) {
    params.set("active_on", activeOn);
  }

  return "/api/salaries?" + params.toString();
}

function renderSalaryRows() {
  document.getElementById("salary-rows").innerHTML = salaryRows
    .map(function (salary) {
      const id = Number(salary.id);
      const employee = salary.employee || {};
      const employeeId = Number(salary.employee_id);
      const history =
        '<a class="link" href="/pages/employee-salaries.html?employee_id=' +
        employeeId + '">History</a>';
      const edit = canManageSalary(salaryPageUser)
        ? '<a class="link" href="/pages/salary-form.html?id=' + id + '">Edit</a>'
        : "";

      return (
        "<tr>" +
        "<td>" + escapeHtml(salaryEmployeeName(employee)) + "</td>" +
        "<td>" + escapeHtml(salaryValueOrDash(employee.employee_code)) + "</td>" +
        "<td>" + escapeHtml(formatSalaryAmount(salary.annual_salary)) + "</td>" +
        "<td>" + escapeHtml(salary.monthly_gross_salary == null ? "-" : formatSalaryAmount(salary.monthly_gross_salary)) + "</td>" +
        "<td>" + escapeHtml(salary.currency) + "</td>" +
        "<td>" + escapeHtml(salaryValueOrDash(salary.effective_from)) + "</td>" +
        "<td>" + escapeHtml(salaryValueOrDash(salary.effective_to)) + "</td>" +
        '<td class="actions-cell">' + history + " " + edit + "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("empty").hidden = salaryRows.length !== 0;
  renderSalaryPagination();
}

function renderSalaryPagination() {
  const info = document.getElementById("page-info");
  if (salaryTotal === 0) {
    info.textContent = "No records";
  } else {
    const first = salaryOffset + 1;
    const last = Math.min(salaryOffset + SALARY_PAGE_SIZE, salaryTotal);
    info.textContent =
      "Showing " + first + "-" + last + " of " + salaryTotal;
  }

  document.getElementById("previous-page").disabled = salaryOffset <= 0;
  document.getElementById("next-page").disabled =
    salaryOffset + SALARY_PAGE_SIZE >= salaryTotal;
}

async function loadSalaryEmployees() {
  const result = await apiGet("/api/salaries/employees");
  if (!handleApiResult(result)) {
    return;
  }

  const select = document.getElementById("employee-filter");
  const selected = select.value;
  const employees = Array.isArray(result.data.employees)
    ? result.data.employees
    : [];

  select.innerHTML = '<option value="">All employees</option>';
  employees.forEach(function (employee) {
    const option = document.createElement("option");
    option.value = String(employee.id);
    option.textContent =
      salaryEmployeeName(employee) + " (" + employee.employee_code + ")";
    select.appendChild(option);
  });

  if (selected) {
    select.value = selected;
  }
}

async function loadSalaries() {
  const result = await apiGet(salaryQuery());
  if (!handleApiResult(result)) {
    return;
  }

  salaryRows = Array.isArray(result.data.salaries) ? result.data.salaries : [];
  salaryTotal = Number(result.data.total) || 0;
  renderSalaryRows();
}

function resetFilters() {
  document.getElementById("search").value = "";
  document.getElementById("employee-filter").value = "";
  document.getElementById("currency-filter").value = "";
  document.getElementById("active-on").value = "";
  salaryOffset = 0;
  loadSalaries();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  salaryPageUser = user;
  initShell(user, "salaries");
  showFlash();

  if (!canReadSalary(user)) {
    showMessage("error", "Your role does not grant access to salary records.");
    return;
  }

  if (!canManageSalary(user)) {
    document.getElementById("create-link").hidden = true;
  }

  document.getElementById("search").addEventListener("input", function () {
    window.clearTimeout(salarySearchTimer);
    salarySearchTimer = window.setTimeout(function () {
      salaryOffset = 0;
      loadSalaries();
    }, 300);
  });

  document.getElementById("employee-filter").addEventListener("change", function () {
    salaryOffset = 0;
    loadSalaries();
  });

  document.getElementById("currency-filter").addEventListener("change", function () {
    salaryOffset = 0;
    loadSalaries();
  });

  document.getElementById("active-on").addEventListener("change", function () {
    salaryOffset = 0;
    loadSalaries();
  });

  document.getElementById("reset-filters").addEventListener("click", resetFilters);

  document.getElementById("previous-page").addEventListener("click", function () {
    salaryOffset = Math.max(0, salaryOffset - SALARY_PAGE_SIZE);
    loadSalaries();
  });

  document.getElementById("next-page").addEventListener("click", function () {
    salaryOffset += SALARY_PAGE_SIZE;
    loadSalaries();
  });

  await loadSalaryEmployees();
  await loadSalaries();
})();
