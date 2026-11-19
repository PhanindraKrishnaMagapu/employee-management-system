// JML event list: scoped events, checklist progress, and detail links.

let allJmlEvents = [];

function jmlEmployeeName(event) {
  const employee = event.employee;
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

function matchesJmlSearch(event, term) {
  if (!term) {
    return true;
  }
  const employee = event.employee || {};
  const text = [
    event.event_type,
    event.effective_date,
    event.status,
    employee.employee_code,
    employee.first_name,
    employee.last_name,
    jmlEmployeeName(event),
  ]
    .join(" ")
    .toLowerCase();
  return text.indexOf(term) !== -1;
}

function jmlBadge(status) {
  return '<span class="badge">' + escapeHtml(status || "-") + "</span>";
}

function renderJmlRows() {
  const term = document.getElementById("search").value.trim().toLowerCase();
  const rows = allJmlEvents.filter(function (event) {
    return matchesJmlSearch(event, term);
  });

  document.getElementById("event-rows").innerHTML = rows
    .map(function (event) {
      const id = Number(event.id);
      const progress =
        Number(event.checklist_done || 0) +
        " / " +
        Number(event.checklist_total || 0);
      const employee = event.employee || {};

      return (
        "<tr>" +
        "<td>" + jmlBadge(event.event_type) + "</td>" +
        "<td>" +
          escapeHtml(jmlEmployeeName(event)) +
          "<br><span class=\"tree-meta\">" +
          escapeHtml(employee.employee_code || "-") +
          "</span>" +
        "</td>" +
        "<td>" + escapeHtml(event.effective_date) + "</td>" +
        "<td>" + jmlBadge(event.status) + "</td>" +
        "<td>" + escapeHtml(progress) + "</td>" +
        '<td class="actions-cell">' +
          '<a class="link" href="/pages/jml-detail.html?id=' + id + '">View</a>' +
        "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("empty").hidden = rows.length !== 0;
}

async function loadJmlEvents() {
  const result = await apiGet("/api/jml/events");
  if (!handleApiResult(result)) {
    return;
  }
  allJmlEvents = Array.isArray(result.data.events) ? result.data.events : [];
  renderJmlRows();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "jml");
  showFlash();

  if (!canReadJml(user)) {
    document.getElementById("create-link").hidden = true;
    showMessage("error", "Your role does not grant access to JML events.");
    return;
  }

  if (!canManageJml(user)) {
    document.getElementById("create-link").hidden = true;
  } else {
    document.getElementById("create-link").hidden = false;
  }

  document.getElementById("search").addEventListener("input", renderJmlRows);
  await loadJmlEvents();
})();
