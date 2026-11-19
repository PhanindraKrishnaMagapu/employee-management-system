// Project detail: summary, assignments, removal, and employee assignment.

let projectDetailUser = null;
let projectDetailId = null;
let projectDetailData = null;
let projectAssignableEmployees = [];

function projectValueOrDash(value) {
  return value === null || value === undefined || value === ""
    ? "-"
    : String(value);
}

function projectEmployeeName(employee) {
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

function renderProjectSummary(project) {
  const rows = [
    ["Project code", project.project_code],
    ["Project name", project.name],
    ["Status", project.status],
    ["Start date", project.start_date],
    ["End date", project.end_date],
    ["Assignments", Number(project.assignment_count || 0)],
  ];
  if (project.description) {
    rows.push(["Description", project.description]);
  }

  document.getElementById("project-summary").innerHTML = rows
    .map(function (row, index) {
      const className = index === rows.length - 1 && row[0] === "Description"
        ? ' class="description"'
        : "";
      return (
        "<div" + className + ">" +
        '<span class="label">' + escapeHtml(row[0]) + "</span>" +
        escapeHtml(projectValueOrDash(row[1])) +
        "</div>"
      );
    })
    .join("");
}

function renderProjectAssignments(assignments) {
  const rows = Array.isArray(assignments) ? assignments : [];
  const tbody = document.getElementById("assignment-rows");

  tbody.innerHTML = rows
    .map(function (assignment) {
      const employee = assignment.employee || {};
      const remove = canManageProjects(projectDetailUser)
        ? '<button type="button" class="link danger" data-remove="' +
          Number(assignment.id) +
          '">Remove</button>'
        : "";

      return (
        "<tr>" +
        "<td>" + escapeHtml(projectEmployeeName(employee)) + "</td>" +
        "<td>" + escapeHtml(employee.employee_code || "-") + "</td>" +
        "<td>" + escapeHtml(projectValueOrDash(assignment.start_date)) + "</td>" +
        "<td>" + escapeHtml(projectValueOrDash(assignment.end_date)) + "</td>" +
        '<td class="allocation-cell">' +
          escapeHtml(Number(assignment.allocation_percentage || 0)) + "%" +
        "</td>" +
        '<td class="actions-cell">' + remove + "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("assignment-empty").hidden = rows.length !== 0;

  tbody.querySelectorAll("[data-remove]").forEach(function (button) {
    button.addEventListener("click", async function () {
      await removeProjectAssignment(Number(button.getAttribute("data-remove")));
    });
  });
}

async function loadProjectDetail() {
  const result = await apiGet("/api/projects/" + projectDetailId);
  if (!handleApiResult(result)) {
    return false;
  }

  projectDetailData = result.data;
  renderProjectSummary(result.data.project);
  renderProjectAssignments(result.data.assignments);
  return true;
}

function renderAssignableEmployees() {
  const select = document.getElementById("employee");
  const assignedIds = new Set(
    ((projectDetailData && projectDetailData.assignments) || []).map(function (item) {
      return Number(item.employee_id);
    })
  );
  const options = projectAssignableEmployees.filter(function (employee) {
    return !assignedIds.has(Number(employee.id));
  });

  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = options.length
    ? "Select an employee"
    : "No additional active employees available";
  select.appendChild(placeholder);

  options.forEach(function (employee) {
    const option = document.createElement("option");
    option.value = String(employee.id);
    option.textContent =
      employee.employee_code +
      " - " +
      projectEmployeeName(employee) +
      " (" +
      employee.employment_status +
      ")";
    select.appendChild(option);
  });

  document.getElementById("assign-button").disabled = options.length === 0;
}

async function loadAssignableEmployees() {
  if (
    !canManageProjects(projectDetailUser) ||
    !canSelectProjectEmployees(projectDetailUser)
  ) {
    return;
  }

  const result = await apiGet("/api/projects/assignable-employees");
  if (!handleApiResult(result)) {
    return;
  }
  projectAssignableEmployees = Array.isArray(result.data.employees)
    ? result.data.employees
    : [];
  renderAssignableEmployees();
}

async function assignProjectEmployee(event) {
  event.preventDefault();
  showMessage("error", "");

  const payload = {
    employee_id: Number(document.getElementById("employee").value),
    start_date: document.getElementById("assignment-start").value,
    end_date: document.getElementById("assignment-end").value || null,
    allocation_percentage: Number(document.getElementById("allocation").value),
  };
  if (!payload.employee_id || !payload.start_date) {
    showMessage("error", "Select an employee and a start date.");
    return;
  }

  const button = document.getElementById("assign-button");
  button.disabled = true;
  const result = await apiPost(
    "/api/projects/" + projectDetailId + "/assignments",
    payload
  );
  button.disabled = false;

  if (!handleApiResult(result)) {
    return;
  }

  showMessage("success", result.data.message || "Employee assigned to project.");
  document.getElementById("assignment-start").value = "";
  document.getElementById("assignment-end").value = "";
  document.getElementById("allocation").value = "100";
  await loadProjectDetail();
  await loadAssignableEmployees();
}

async function removeProjectAssignment(assignmentId) {
  if (!window.confirm("Remove this employee from the project?")) {
    return;
  }

  showMessage("error", "");
  const result = await apiDelete(
    "/api/projects/" + projectDetailId + "/assignments/" + assignmentId
  );
  if (!handleApiResult(result)) {
    return;
  }

  showMessage("success", result.data.message || "Employee assignment removed.");
  await loadProjectDetail();
  await loadAssignableEmployees();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  projectDetailUser = user;
  initShell(user, "projects");
  showFlash();

  if (!canReadProjects(user)) {
    showMessage("error", "Your role does not grant access to projects.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  projectDetailId = Number(params.get("id"));
  if (!Number.isInteger(projectDetailId) || projectDetailId <= 0) {
    showMessage("error", "No project was selected.");
    return;
  }

  const editLink = document.getElementById("edit-link");
  if (canManageProjects(user)) {
    editLink.href = "/pages/project-form.html?id=" + projectDetailId;
  } else {
    editLink.hidden = true;
  }

  if (canManageProjects(user) && canSelectProjectEmployees(user)) {
    document.getElementById("assignment-panel").hidden = false;
    document.getElementById("assignment-form").addEventListener(
      "submit",
      assignProjectEmployee
    );
  }

  const loaded = await loadProjectDetail();
  if (loaded) {
    await loadAssignableEmployees();
  }
})();
