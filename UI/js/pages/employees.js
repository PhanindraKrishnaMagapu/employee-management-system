// Role-scoped employee directory with client-side filters and pagination.

let allEmployees = [];
let pageUser = null;
let directoryPage = 1;
const DIRECTORY_PAGE_SIZE = 10;

function matchesSearch(employee, term) {
  if (!term) {
    return true;
  }
  const text = [
    employee.employee_code,
    employee.first_name,
    employee.last_name,
    employee.first_name + " " + employee.last_name,
    employee.official_email,
  ].join(" ").toLowerCase();
  return text.includes(term);
}

function safeEmployeePhoto(path) {
  if (typeof path !== "string" || !path.trim()) {
    return null;
  }
  const value = path.trim();
  if (value.startsWith("//") || value.includes("\\") || /^[a-z][a-z0-9+.-]*:/i.test(value)) {
    return null;
  }
  try {
    const url = new URL(value.startsWith("/") ? value : "/" + value, window.location.origin);
    return url.origin === window.location.origin ? url.href : null;
  } catch (error) {
    return null;
  }
}

function employeeAvatar(employee, sizeClass) {
  const name = [employee.first_name, employee.last_name].filter(Boolean).join(" ");
  const initial = (name || employee.employee_code || "?").trim().charAt(0).toUpperCase();
  const photo = safeEmployeePhoto(employee.profile_photo_path);
  const image = photo
    ? '<img src="' + escapeHtml(photo) + '" alt="" loading="lazy" referrerpolicy="no-referrer">'
    : "";
  return '<span class="directory-avatar ' + sizeClass + '" aria-hidden="true">' +
    escapeHtml(initial) + image + "</span>";
}

function populateDirectoryFilters() {
  const departmentSelect = document.getElementById("department-filter");
  const departments = Array.from(new Set(allEmployees
    .map(function (employee) { return employee.department_id; })
    .filter(function (value) { return value !== null && value !== undefined; })
    .map(String)))
    .sort(function (left, right) { return left.localeCompare(right, undefined, { numeric: true }); });
  departmentSelect.innerHTML = '<option value="">All departments</option>' + departments
    .map(function (departmentId) {
      return '<option value="' + escapeHtml(departmentId) + '">Department ID ' +
        escapeHtml(departmentId) + "</option>";
    })
    .join("");

  const statusSelect = document.getElementById("status-filter");
  const statuses = Array.from(new Set(allEmployees
    .map(function (employee) { return employee.employment_status; })
    .filter(Boolean)))
    .sort();
  statusSelect.innerHTML = '<option value="">All statuses</option>' + statuses
    .map(function (status) {
      return '<option value="' + escapeHtml(status) + '">' + escapeHtml(status) + "</option>";
    })
    .join("");
}

function filteredEmployees() {
  const term = document.getElementById("search").value.trim().toLowerCase();
  const departmentId = document.getElementById("department-filter").value;
  const status = document.getElementById("status-filter").value;
  return allEmployees.filter(function (employee) {
    return matchesSearch(employee, term) &&
      (!departmentId || String(employee.department_id) === departmentId) &&
      (!status || employee.employment_status === status);
  });
}

function employeeActions(employee) {
  const id = Number(employee.id);
  const profile = '<a href="/pages/employee-profile.html?id=' + id + '">View profile</a>';
  const edit = canEdit(pageUser)
    ? '<a href="/pages/employee-form.html?id=' + id + '">Edit employee</a>'
    : "";
  const skills = canReadSkills(pageUser)
    ? '<a href="/pages/employee-skills.html?employee_id=' + id + '">Skills</a>'
    : "";
  const salary = canReadSalary(pageUser)
    ? '<a href="/pages/employee-salaries.html?employee_id=' + id + '">Salary history</a>'
    : "";
  const archive = canArchive(pageUser)
    ? '<button type="button" class="link danger" data-archive="' + id + '">Archive</button>'
    : "";
  return (
    '<details class="directory-actions"><summary class="button">Actions</summary>' +
      '<div class="directory-action-menu">' + profile + edit + skills + salary + archive + "</div>" +
    "</details>"
  );
}

function renderRows() {
  const matches = filteredEmployees();
  const pageCount = Math.max(1, Math.ceil(matches.length / DIRECTORY_PAGE_SIZE));
  directoryPage = Math.min(directoryPage, pageCount);
  const startIndex = (directoryPage - 1) * DIRECTORY_PAGE_SIZE;
  const rows = matches.slice(startIndex, startIndex + DIRECTORY_PAGE_SIZE);

  document.getElementById("employee-rows").innerHTML = rows
    .map(function (employee) {
      const id = Number(employee.id);
      const fullName = [employee.first_name, employee.last_name].filter(Boolean).join(" ");
      const profileHref = "/pages/employee-profile.html?id=" + id;
      const statusClass = String(employee.employment_status || "unknown")
        .toLowerCase().replace(/[^a-z0-9]+/g, "-");
      const photo = employeeAvatar(employee, "directory-avatar-small");
      return (
        "<tr>" +
          '<td><a class="directory-employee-link" href="' + profileHref + '">' + photo +
            '<span class="directory-employee-copy"><strong>' + escapeHtml(fullName || "Not available") +
            '</strong><span>' + escapeHtml(employee.designation_id
              ? "Designation ID " + employee.designation_id
              : "Designation not available") + "</span></span></a></td>" +
          "<td>" + escapeHtml(employee.employee_code || "Not available") + "</td>" +
          "<td>" + escapeHtml(employee.department_id === null || employee.department_id === undefined
            ? "Not available"
            : "Department ID " + employee.department_id) + "</td>" +
          '<td><span class="directory-contact">' + escapeHtml(employee.official_email || "Not available") +
            '</span><span class="directory-contact-secondary">' + escapeHtml(employee.phone || "Not available") +
            "</span></td>" +
          '<td><span class="directory-status status-' + escapeHtml(statusClass) + '">' +
            escapeHtml(employee.employment_status || "Not available") + "</span></td>" +
          '<td class="directory-actions-cell">' + employeeActions(employee) + "</td>" +
        "</tr>"
      );
    })
    .join("");

  const firstResult = matches.length ? startIndex + 1 : 0;
  const lastResult = Math.min(startIndex + rows.length, matches.length);
  document.getElementById("directory-results").textContent =
    "Showing " + firstResult + "–" + lastResult + " of " + matches.length;
  document.getElementById("page-info").textContent = "Page " + directoryPage + " of " + pageCount;
  document.getElementById("previous-page").disabled = directoryPage <= 1;
  document.getElementById("next-page").disabled = directoryPage >= pageCount;
  document.getElementById("empty").hidden = rows.length !== 0;

  document.querySelectorAll("[data-archive]").forEach(function (button) {
    button.addEventListener("click", async function () {
      await archiveEmployee(Number(button.getAttribute("data-archive")));
    });
  });
}

async function archiveEmployee(id) {
  if (!window.confirm("Archive this employee? The record is kept but hidden from the list.")) {
    return;
  }

  showMessage("error", "");
  const result = await apiDelete("/api/employees/" + id);
  if (!handleApiResult(result)) {
    return;
  }

  showMessage("success", "Employee archived.");
  await loadEmployees();
}

async function loadEmployees() {
  const result = await apiGet("/api/employees");
  if (!handleApiResult(result)) {
    return;
  }
  allEmployees = result.data.employees || [];
  populateDirectoryFilters();
  renderRows();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  pageUser = user;
  initShell(user, "employees");
  if (!canRead(user)) {
    showMessage("error", "Your role does not grant access to employee records.");
    return;
  }

  if (!canCreate(user)) {
    document.getElementById("add-link").hidden = true;
  }

  showFlash();
  document.getElementById("search").addEventListener("input", function () {
    directoryPage = 1;
    renderRows();
  });
  document.getElementById("department-filter").addEventListener("change", function () {
    directoryPage = 1;
    renderRows();
  });
  document.getElementById("status-filter").addEventListener("change", function () {
    directoryPage = 1;
    renderRows();
  });
  document.getElementById("previous-page").addEventListener("click", function () {
    directoryPage = Math.max(1, directoryPage - 1);
    renderRows();
  });
  document.getElementById("next-page").addEventListener("click", function () {
    directoryPage += 1;
    renderRows();
  });
  await loadEmployees();
})();
