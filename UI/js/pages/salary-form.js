// Create or edit a salary record. Management is enforced by the API as well.

let salaryFormId = null;
let salaryFormEmployeeId = null;

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

function setFormValue(id, value) {
  document.getElementById(id).value =
    value === null || value === undefined ? "" : String(value);
}

function disableSalaryForm(message) {
  document.getElementById("submit-button").disabled = true;
  showMessage("error", message);
}

async function loadEmployeesForCreate() {
  const result = await apiGet("/api/salaries/employees");
  if (!handleApiResult(result)) {
    return false;
  }

  const employees = Array.isArray(result.data.employees)
    ? result.data.employees
    : [];
  const select = document.getElementById("employee");
  select.innerHTML = '<option value="">Select an employee</option>';

  employees.forEach(function (employee) {
    const option = document.createElement("option");
    option.value = String(employee.id);
    option.textContent =
      salaryEmployeeName(employee) + " (" + employee.employee_code + ")";
    select.appendChild(option);
  });

  if (employees.length === 0) {
    disableSalaryForm("No employees are available for a salary record.");
    return false;
  }

  if (salaryFormEmployeeId !== null) {
    const exists = employees.some(function (employee) {
      return Number(employee.id) === salaryFormEmployeeId;
    });
    if (!exists) {
      disableSalaryForm(
        "The selected employee is archived or unavailable for new salary records."
      );
      return false;
    }
    select.value = String(salaryFormEmployeeId);
  }

  return true;
}

async function loadSalaryForEdit() {
  const result = await apiGet("/api/salaries/" + salaryFormId);
  if (!handleApiResult(result)) {
    return false;
  }

  const salary = result.data.salary;
  if (!salary) {
    return false;
  }

  salaryFormEmployeeId = Number(salary.employee_id);
  setFormValue("annual-salary", salary.annual_salary);
  setFormValue("currency", salary.currency || "INR");
  setFormValue("effective-from", salary.effective_from);
  setFormValue("effective-to", salary.effective_to);

  // The employee is immutable on update. Disable the still-required select so
  // native form validation does not block submission while it is hidden.
  document.getElementById("employee").disabled = true;
  document.getElementById("employee-select-field").hidden = true;
  document.getElementById("employee-readonly").hidden = false;
  document.getElementById("employee-summary").textContent =
    salaryEmployeeName(salary.employee) +
    " (" + salaryValueOrDash(salary.employee && salary.employee.employee_code) + ")";
  return true;
}

function collectSalaryPayload() {
  const rawAmount = document.getElementById("annual-salary").value.trim();
  const rawCurrency = document.getElementById("currency").value.trim();
  const effectiveFrom = document.getElementById("effective-from").value;
  const effectiveTo = document.getElementById("effective-to").value;

  if (!rawAmount || !Number.isFinite(Number(rawAmount)) || Number(rawAmount) < 0) {
    showMessage("error", "Annual salary must be a non-negative number.");
    return null;
  }
  if (!/^\d+(\.\d{1,2})?$/.test(rawAmount)) {
    showMessage("error", "Annual salary must have at most two decimal places.");
    return null;
  }
  if (!/^[A-Za-z]{3}$/.test(rawCurrency)) {
    showMessage("error", "Currency must be a three-letter code.");
    return null;
  }
  if (!effectiveFrom) {
    showMessage("error", "Effective from is required.");
    return null;
  }
  if (effectiveTo && effectiveTo < effectiveFrom) {
    showMessage("error", "Effective to must be on or after effective from.");
    return null;
  }

  const payload = {
    annual_salary: Number(rawAmount),
    currency: rawCurrency.toUpperCase(),
    effective_from: effectiveFrom,
    effective_to: effectiveTo || null,
  };

  if (salaryFormId === null) {
    const employeeId = Number(document.getElementById("employee").value);
    if (!Number.isInteger(employeeId) || employeeId <= 0) {
      showMessage("error", "Select an employee.");
      return null;
    }
    payload.employee_id = employeeId;
  }

  return payload;
}

async function submitSalaryForm(event) {
  event.preventDefault();
  showMessage("error", "");

  const payload = collectSalaryPayload();
  if (payload === null) {
    return;
  }

  const button = document.getElementById("submit-button");
  button.disabled = true;

  const result = salaryFormId === null
    ? await apiPost("/api/salaries", payload)
    : await apiPut("/api/salaries/" + salaryFormId, payload);

  button.disabled = false;
  if (!handleApiResult(result)) {
    return;
  }

  const saved = result.data.salary || {};
  const employeeId = Number(saved.employee_id) || salaryFormEmployeeId;
  setFlash("success", "Salary record saved.");

  if (employeeId) {
    window.location.replace(
      "/pages/employee-salaries.html?employee_id=" + employeeId
    );
  } else {
    window.location.replace("/pages/salaries.html");
  }
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "salaries");
  showFlash();

  if (!canManageSalary(user)) {
    disableSalaryForm("Your role does not grant permission to manage salary records.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const rawId = params.get("id");
  const rawEmployeeId = params.get("employee_id");

  if (rawId !== null && rawId !== "") {
    salaryFormId = Number(rawId);
    if (!Number.isInteger(salaryFormId) || salaryFormId <= 0) {
      disableSalaryForm("No valid salary record was selected.");
      return;
    }
    document.getElementById("page-title").textContent = "Edit Salary";
    document.getElementById("page-subtitle").textContent =
      "Update the selected salary period. The employee cannot be changed.";
    document.getElementById("submit-button").textContent = "Save changes";
    const loaded = await loadSalaryForEdit();
    if (!loaded) {
      disableSalaryForm("The selected salary record could not be loaded.");
      return;
    }
  } else {
    if (rawEmployeeId !== null && rawEmployeeId !== "") {
      salaryFormEmployeeId = Number(rawEmployeeId);
      if (!Number.isInteger(salaryFormEmployeeId) || salaryFormEmployeeId <= 0) {
        salaryFormEmployeeId = null;
      }
    }
    document.getElementById("effective-from").value = new Date()
      .toISOString()
      .slice(0, 10);
    const loaded = await loadEmployeesForCreate();
    if (!loaded) {
      return;
    }
  }

  document.getElementById("salary-form").addEventListener("submit", submitSalaryForm);
})();
