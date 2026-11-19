// JML event detail: status actions, checklist tracking, and Mover history.

let jmlDetailUser = null;
let jmlDetailEvent = null;
let jmlDetailEventId = null;

function jmlDetailName(employee) {
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

function valueOrDash(value) {
  return value === null || value === undefined || value === ""
    ? "-"
    : String(value);
}

function renderJmlSummary() {
  const event = jmlDetailEvent;
  const employee = event.employee || {};
  const rows = [
    ["Event type", event.event_type],
    ["Employee", jmlDetailName(employee) + " (" + (employee.employee_code || "-") + ")"],
    ["Effective date", event.effective_date],
    ["Status", event.status],
    [
      "Checklist",
      Number(event.checklist_done || 0) +
        " of " +
        Number(event.checklist_total || 0) +
        " completed",
    ],
  ];

  if (Object.prototype.hasOwnProperty.call(event, "reason")) {
    rows.push([
      event.event_type === "Leaver" ? "Exit reason" : "Reason",
      event.reason || "-",
    ]);
  }

  document.getElementById("event-summary").innerHTML = rows
    .map(function (row) {
      return (
        "<div><span class=\"label\">" +
        escapeHtml(row[0]) +
        "</span>" +
        escapeHtml(valueOrDash(row[1])) +
        "</div>"
      );
    })
    .join("");

  const controls = document.getElementById("manage-controls");
  if (canManageJml(jmlDetailUser)) {
    controls.hidden = false;
    document.getElementById("event-status").value = event.status;
  } else {
    controls.hidden = true;
  }
}

function renderJmlChecklist(items) {
  const container = document.getElementById("checklist");
  if (!items || items.length === 0) {
    container.innerHTML = '<li class="empty">No checklist items found.</li>';
    return;
  }

  container.innerHTML = items
    .map(function (item) {
      const id = Number(item.id);
      const nextStatus = item.status === "Completed" ? "Pending" : "Completed";
      const action = canManageJml(jmlDetailUser)
        ? '<button type="button" class="link" data-item-id="' +
          id +
          '" data-next-status="' +
          escapeHtml(nextStatus) +
          '">' +
          (nextStatus === "Completed" ? "Mark complete" : "Mark pending") +
          "</button>"
        : "";

      return (
        "<li>" +
        '<span class="title">' + escapeHtml(item.title) + "</span>" +
        '<span class="description">' + escapeHtml(valueOrDash(item.description)) + "</span>" +
        '<span class="badge">' + escapeHtml(item.status) + "</span>" +
        '<span class="actions-cell">' + action + "</span>" +
        "</li>"
      );
    })
    .join("");

  container.querySelectorAll("[data-item-id]").forEach(function (button) {
    button.addEventListener("click", async function () {
      await updateChecklistItem(
        Number(button.getAttribute("data-item-id")),
        button.getAttribute("data-next-status")
      );
    });
  });
}

function historyPair(oldValue, newValue) {
  const oldText = valueOrDash(oldValue);
  const newText = valueOrDash(newValue);
  return oldText === newText ? newText : oldText + " -> " + newText;
}

function renderJmlHistory(history) {
  const panel = document.getElementById("history-panel");
  if (
    jmlDetailEvent.event_type !== "Mover" ||
    !Array.isArray(history) ||
    history.length === 0
  ) {
    panel.hidden = true;
    return;
  }

  panel.hidden = false;
  document.getElementById("history-rows").innerHTML = history
    .map(function (row) {
      return (
        "<tr>" +
        "<td>" + escapeHtml(row.effective_date) + "</td>" +
        "<td>" + escapeHtml(historyPair(row.old_department_id, row.new_department_id)) + "</td>" +
        "<td>" + escapeHtml(historyPair(row.old_designation_id, row.new_designation_id)) + "</td>" +
        "<td>" + escapeHtml(historyPair(row.old_manager_id, row.new_manager_id)) + "</td>" +
        "<td>" + escapeHtml(historyPair(row.old_location, row.new_location)) + "</td>" +
        "<td>" + escapeHtml(valueOrDash(row.change_reason)) + "</td>" +
        "</tr>"
      );
    })
    .join("");
}

async function loadJmlDetail() {
  const result = await apiGet("/api/jml/events/" + jmlDetailEventId);
  if (!handleApiResult(result)) {
    return;
  }

  jmlDetailEvent = result.data.event;
  renderJmlSummary();
  renderJmlChecklist(result.data.checklist_items);
  renderJmlHistory(result.data.history);
}

async function updateEventStatus() {
  const button = document.getElementById("update-status");
  button.disabled = true;
  showMessage("error", "");

  const result = await apiRequest(
    "/api/jml/events/" + jmlDetailEventId,
    { method: "PATCH", body: { status: document.getElementById("event-status").value } }
  );
  button.disabled = false;

  if (!handleApiResult(result)) {
    return;
  }
  showMessage("success", result.data.message || "JML event updated.");
  await loadJmlDetail();
}

async function updateChecklistItem(itemId, status) {
  showMessage("error", "");
  const result = await apiRequest(
    "/api/jml/events/" + jmlDetailEventId + "/checklist/" + itemId,
    { method: "PATCH", body: { status: status } }
  );
  if (!handleApiResult(result)) {
    return;
  }
  showMessage("success", result.data.message || "Checklist item updated.");
  await loadJmlDetail();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  jmlDetailUser = user;
  initShell(user, "jml");
  showFlash();

  if (!canReadJml(user)) {
    showMessage("error", "Your role does not grant access to JML events.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  jmlDetailEventId = Number(params.get("id"));
  if (!Number.isInteger(jmlDetailEventId) || jmlDetailEventId <= 0) {
    showMessage("error", "No JML event was selected.");
    return;
  }

  document.getElementById("update-status").addEventListener("click", updateEventStatus);
  await loadJmlDetail();
})();
