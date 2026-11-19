// Create or edit a project. Management is enforced by the API as well.

let projectFormId = null;

function setFormValue(id, value) {
  document.getElementById(id).value =
    value === null || value === undefined ? "" : String(value);
}

function collectProjectFormPayload() {
  const payload = {
    project_code: document.getElementById("project-code").value.trim(),
    name: document.getElementById("project-name").value.trim(),
    description: document.getElementById("description").value.trim() || null,
    status: document.getElementById("status").value,
    start_date: document.getElementById("start-date").value || null,
    end_date: document.getElementById("end-date").value || null,
  };
  return payload;
}

function disableProjectForm(message) {
  document.getElementById("submit-button").disabled = true;
  showMessage("error", message);
}

async function loadProjectForEdit() {
  const result = await apiGet("/api/projects/" + projectFormId);
  if (!handleApiResult(result)) {
    return false;
  }

  const project = result.data.project;
  setFormValue("project-code", project.project_code);
  setFormValue("project-name", project.name);
  setFormValue("description", project.description);
  setFormValue("status", project.status);
  setFormValue("start-date", project.start_date);
  setFormValue("end-date", project.end_date);
  return true;
}

async function submitProjectForm(event) {
  event.preventDefault();
  showMessage("error", "");

  const payload = collectProjectFormPayload();
  const button = document.getElementById("submit-button");
  button.disabled = true;

  const result = projectFormId === null
    ? await apiPost("/api/projects", payload)
    : await apiPut("/api/projects/" + projectFormId, payload);

  button.disabled = false;
  if (!handleApiResult(result)) {
    return;
  }

  setFlash("success", result.data.message || "Project saved.");
  const projectId = projectFormId === null
    ? Number(result.data.project.id)
    : projectFormId;
  window.location.replace("/pages/project-detail.html?id=" + projectId);
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "projects");
  showFlash();

  if (!canManageProjects(user)) {
    disableProjectForm("Your role does not grant permission to manage projects.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const rawId = params.get("id");
  if (rawId !== null && rawId !== "") {
    projectFormId = Number(rawId);
    if (!Number.isInteger(projectFormId) || projectFormId <= 0) {
      disableProjectForm("No valid project was selected.");
      return;
    }
    document.getElementById("page-title").textContent = "Edit Project";
    document.getElementById("page-subtitle").textContent =
      "Update the selected project's details.";
    document.getElementById("submit-button").textContent = "Save changes";
    const loaded = await loadProjectForEdit();
    if (!loaded) {
      disableProjectForm("The selected project could not be loaded.");
      return;
    }
  }

  document.getElementById("project-form").addEventListener(
    "submit",
    submitProjectForm
  );
})();
