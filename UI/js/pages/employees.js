// Employee list: loading, client-side search, and archive action.

let allEmployees = [];
let pageUser = null;

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
  ]
    .join(" ")
    .toLowerCase();
  return text.indexOf(term) !== -1;
}

function renderRows() {
  const term = document.getElementById("search").value.trim().toLowerCase();
  const rows = allEmployees.filter(function (employee) {
    return matchesSearch(employee, term);
  });

  document.getElementById("employee-rows").innerHTML = rows
    .map(function (employee) {
      const id = Number(employee.id);
      const edit = canEdit(pageUser)
        ? '<a class="link" href="/pages/employee-form.html?id=' + id + '">Edit</a>'
        : "";
      const archive = canArchive(pageUser)
        ? '<button type="button" class="link danger" data-archive="' + id + '">Archive</button>'
        : "";

      return (
        "<tr>" +
        "<td>" + escapeHtml(employee.employee_code) + "</td>" +
        "<td>" + escapeHtml(employee.first_name) + " " + escapeHtml(employee.last_name) + "</td>" +
        "<td>" + escapeHtml(employee.official_email) + "</td>" +
        "<td>" + escapeHtml(employee.phone || "-") + "</td>" +
        "<td>" + escapeHtml(employee.employment_status) + "</td>" +
        '<td class="actions-cell">' + edit + " " + archive + "</td>" +
        "</tr>"
      );
    })
    .join("");

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
  document.getElementById("search").addEventListener("input", renderRows);
  await loadEmployees();
})();
