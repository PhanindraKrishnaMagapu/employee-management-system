// Shared add/edit form. Fields are derived from the caller's permissions.

const FIELD_META = {
  employee_code: { label: "Employee code", type: "text", required: true },
  first_name: { label: "First name", type: "text", required: true },
  last_name: { label: "Last name", type: "text", required: true },
  official_email: { label: "Official email", type: "email", required: true },
  phone: { label: "Phone", type: "tel", required: false },
  joining_date: { label: "Joining date", type: "date", required: true },
  employment_type: { label: "Employment type", type: "text", required: true },
  employment_status: {
    label: "Employment status",
    type: "select",
    options: ["Pre-joining", "Active", "Exited"],
    required: true,
  },
  location: { label: "Location", type: "text", required: false },
  department_id: { label: "Department ID", type: "number", min: 1, required: true },
  designation_id: { label: "Designation ID", type: "number", min: 1, required: true },
  manager_id: { label: "Manager ID", type: "number", min: 1, required: false },
  profile_photo_path: { label: "Profile photo path", type: "text", required: false },
};

let formFields = [];
let editingId = null;

function buildField(name, value) {
  const meta = FIELD_META[name];
  const label = document.createElement("label");
  label.textContent = meta.label + (meta.required ? " *" : "");

  let control;
  if (meta.type === "select") {
    control = document.createElement("select");
    meta.options.forEach(function (option) {
      const item = document.createElement("option");
      item.value = option;
      item.textContent = option;
      control.appendChild(item);
    });
  } else {
    control = document.createElement("input");
    control.type = meta.type;
    if (meta.min !== undefined) {
      control.min = String(meta.min);
    }
  }

  control.id = "field-" + name;
  control.name = name;
  control.required = Boolean(meta.required);

  if (value !== undefined && value !== null) {
    control.value = String(value);
  } else if (name === "employment_status") {
    control.value = "Active";
  }

  label.appendChild(control);
  return label;
}

function renderFields(values) {
  const container = document.getElementById("fields");
  container.innerHTML = "";
  formFields.forEach(function (name) {
    container.appendChild(buildField(name, values[name]));
  });
}

function collectValues() {
  const values = {};
  formFields.forEach(function (name) {
    const control = document.getElementById("field-" + name);
    const meta = FIELD_META[name];
    const raw = control.value;

    if (meta.type === "number") {
      values[name] = raw === "" ? null : Number(raw);
    } else {
      values[name] = raw;
    }
  });
  return values;
}

function disableForm(message) {
  document.getElementById("submit-button").disabled = true;
  showMessage("error", message);
}

async function submitForm(event) {
  event.preventDefault();
  showMessage("error", "");

  const button = document.getElementById("submit-button");
  button.disabled = true;
  const values = collectValues();
  const result = editingId
    ? await apiPut("/api/employees/" + editingId, values)
    : await apiPost("/api/employees", values);
  button.disabled = false;

  if (!handleApiResult(result)) {
    return;
  }

  setFlash("success", result.data.message || "Employee saved.");
  window.location.replace("/pages/employees.html");
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  editingId = id ? Number(id) : null;

  initShell(user, editingId ? "employees" : "add");

  const form = document.getElementById("employee-form");
  form.addEventListener("submit", submitForm);

  if (!editingId) {
    if (!canCreate(user)) {
      disableForm("Your role does not grant permission to add employees.");
      return;
    }
    formFields = CREATE_FORM_FIELDS.slice();
    document.getElementById("form-title").textContent = "Add employee";
    document.getElementById("form-subtitle").textContent = "Fields marked * are required.";
    renderFields({});
    return;
  }

  if (!canEdit(user)) {
    disableForm("Your role does not grant permission to edit employees.");
    return;
  }

  formFields = editableFieldsFor(user);
  if (formFields.length === 0) {
    disableForm("Your role does not grant permission to edit employee fields.");
    return;
  }

  const result = await apiGet("/api/employees/" + editingId);
  if (!handleApiResult(result)) {
    return;
  }

  document.getElementById("form-title").textContent = "Edit employee";
  document.getElementById("form-subtitle").textContent =
    "Only fields allowed for your role are shown.";
  renderFields(result.data.employee || {});
})();
