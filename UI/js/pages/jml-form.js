// Create a Joiner, Mover, or Leaver event for an employee in the user's scope.

const MOVER_FIELD_IDS = [
  "field-department_id",
  "field-designation_id",
  "field-manager_id",
  "field-location",
];

let jmlFormEmployees = [];

function jmlFormName(employee) {
  const name = [employee.first_name, employee.last_name]
    .filter(function (part) {
      return part !== null && part !== undefined && String(part).trim() !== "";
    })
    .join(" ");
  return name || employee.employee_code;
}

function renderEmployeeOptions() {
  const select = document.getElementById("employee");
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select an employee";
  select.appendChild(placeholder);

  jmlFormEmployees.forEach(function (employee) {
    const option = document.createElement("option");
    option.value = String(employee.id);
    option.textContent =
      employee.employee_code +
      " - " +
      jmlFormName(employee) +
      " (" +
      employee.employment_status +
      ")";
    select.appendChild(option);
  });
}

function selectedEmployee() {
  const value = document.getElementById("employee").value;
  if (value === "") {
    return null;
  }
  const id = Number(value);
  return jmlFormEmployees.find(function (employee) {
    return Number(employee.id) === id;
  }) || null;
}

function setFieldValue(id, value) {
  document.getElementById(id).value =
    value === null || value === undefined ? "" : String(value);
}

function syncMoverFields() {
  const employee = selectedEmployee();
  if (!employee) {
    MOVER_FIELD_IDS.forEach(function (id) {
      setFieldValue(id, "");
    });
    return;
  }

  setFieldValue("field-department_id", employee.department_id);
  setFieldValue("field-designation_id", employee.designation_id);
  setFieldValue("field-manager_id", employee.manager_id);
  setFieldValue("field-location", employee.location);
}

function updateFormMode() {
  const eventType = document.getElementById("event-type").value;
  const isMover = eventType === "Mover";
  const isLeaver = eventType === "Leaver";

  document.getElementById("mover-fields").hidden = !isMover;
  document.getElementById("field-department_id").required = isMover;
  document.getElementById("field-designation_id").required = isMover;
  document.getElementById("reason-label-text").textContent = isLeaver
    ? "Exit reason *"
    : "Reason (optional)";
  document.getElementById("reason").required = isLeaver;

  if (isMover) {
    syncMoverFields();
  }
}

function collectMoverChanges(employee) {
  const changes = {};
  if (!employee) {
    return changes;
  }

  const departmentId = Number(document.getElementById("field-department_id").value);
  const designationId = Number(document.getElementById("field-designation_id").value);
  const managerRaw = document.getElementById("field-manager_id").value;
  const managerId = managerRaw === "" ? null : Number(managerRaw);
  const location = document.getElementById("field-location").value.trim() || null;
  const currentManagerId = employee.manager_id === null || employee.manager_id === undefined
    ? null
    : Number(employee.manager_id);

  if (departmentId !== Number(employee.department_id)) {
    changes.department_id = departmentId;
  }
  if (designationId !== Number(employee.designation_id)) {
    changes.designation_id = designationId;
  }
  if (managerId !== currentManagerId) {
    changes.manager_id = managerId;
  }
  if (location !== (employee.location || null)) {
    changes.location = location;
  }

  return changes;
}

function collectPayload() {
  const payload = {
    employee_id: Number(document.getElementById("employee").value),
    event_type: document.getElementById("event-type").value,
    effective_date: document.getElementById("effective-date").value,
    reason: document.getElementById("reason").value.trim() || null,
  };

  if (payload.event_type === "Mover") {
    payload.changes = collectMoverChanges(selectedEmployee());
  }

  return payload;
}

function disableForm(message) {
  document.getElementById("submit-button").disabled = true;
  showMessage("error", message);
}

async function submitForm(event) {
  event.preventDefault();
  showMessage("error", "");

  const payload = collectPayload();
  if (payload.event_type === "Mover" && Object.keys(payload.changes).length === 0) {
    showMessage("error", "Change at least one Mover field before submitting.");
    return;
  }

  const button = document.getElementById("submit-button");
  button.disabled = true;
  const result = await apiPost("/api/jml/events", payload);
  button.disabled = false;

  if (!handleApiResult(result)) {
    return;
  }

  setFlash("success", result.data.message || "JML event created.");
  window.location.replace(
    "/pages/jml-detail.html?id=" + Number(result.data.event.id)
  );
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "jml");
  showFlash();

  if (!canManageJml(user)) {
    disableForm("Your role does not grant permission to manage JML events.");
    return;
  }

  document.getElementById("event-type").addEventListener("change", updateFormMode);
  document.getElementById("employee").addEventListener("change", function () {
    if (document.getElementById("event-type").value === "Mover") {
      syncMoverFields();
    }
  });
  document.getElementById("jml-form").addEventListener("submit", submitForm);
  updateFormMode();

  const result = await apiGet("/api/employees");
  if (!handleApiResult(result)) {
    return;
  }

  jmlFormEmployees = Array.isArray(result.data.employees)
    ? result.data.employees
    : [];
  if (jmlFormEmployees.length === 0) {
    disableForm("No employees are available for JML events.");
    return;
  }

  renderEmployeeOptions();
})();
