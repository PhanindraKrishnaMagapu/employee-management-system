// Project list: search, assignment counts, and management links.

let allProjects = [];
let projectsPageUser = null;

function projectValueOrDash(value) {
  return value === null || value === undefined || value === ""
    ? "-"
    : String(value);
}

function matchesProjectSearch(project, term) {
  if (!term) {
    return true;
  }
  return [
    project.project_code,
    project.name,
    project.status,
    project.start_date,
    project.end_date,
  ]
    .join(" ")
    .toLowerCase()
    .indexOf(term) !== -1;
}

function renderProjectRows() {
  const term = document.getElementById("search").value.trim().toLowerCase();
  const rows = allProjects.filter(function (project) {
    return matchesProjectSearch(project, term);
  });

  document.getElementById("project-rows").innerHTML = rows
    .map(function (project) {
      const id = Number(project.id);
      const edit = canManageProjects(projectsPageUser)
        ? '<a class="link" href="/pages/project-form.html?id=' + id + '">Edit</a>'
        : "";

      return (
        "<tr>" +
        "<td>" + escapeHtml(project.project_code) + "</td>" +
        "<td>" + escapeHtml(project.name) + "</td>" +
        '<td><span class="badge">' + escapeHtml(project.status) + "</span></td>" +
        "<td>" + escapeHtml(projectValueOrDash(project.start_date)) + "</td>" +
        "<td>" + escapeHtml(projectValueOrDash(project.end_date)) + "</td>" +
        "<td>" + escapeHtml(Number(project.assignment_count || 0)) + "</td>" +
        '<td class="actions-cell">' +
          '<a class="link" href="/pages/project-detail.html?id=' + id + '">View</a> ' +
          edit +
        "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("empty").hidden = rows.length !== 0;
}

async function loadProjects() {
  const result = await apiGet("/api/projects");
  if (!handleApiResult(result)) {
    return;
  }
  allProjects = Array.isArray(result.data.projects) ? result.data.projects : [];
  renderProjectRows();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  projectsPageUser = user;
  initShell(user, "projects");
  showFlash();

  if (!canReadProjects(user)) {
    showMessage("error", "Your role does not grant access to projects.");
    return;
  }

  if (!canManageProjects(user)) {
    document.getElementById("create-link").hidden = true;
  }

  document.getElementById("search").addEventListener("input", renderProjectRows);
  await loadProjects();
})();
