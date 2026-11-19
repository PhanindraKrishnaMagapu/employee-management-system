// Organizational tree built exclusively from the authorized employee roster.
// The backend applies employee RBAC and subtree scope before data reaches here.

let hierarchyEmployees = [];
let hierarchyTree = null;
let selectedHierarchyId = null;
let focusHierarchyId = null;
let hierarchyQuery = "";

function hierarchyManagerId(employee) {
  if (employee.manager_id === null || employee.manager_id === undefined || employee.manager_id === "") {
    return null;
  }
  const id = Number(employee.manager_id);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function hierarchyName(employee) {
  return [employee.first_name, employee.last_name]
    .filter(function (part) { return part !== null && part !== undefined && String(part).trim(); })
    .join(" ") || employee.employee_code || "Employee";
}

function buildHierarchy(employees) {
  const byId = new Map();
  employees.forEach(function (employee) {
    const id = Number(employee.id);
    if (Number.isSafeInteger(id) && id > 0) byId.set(id, employee);
  });

  const parent = new Map();
  const brokenCycles = new Set();
  byId.forEach(function (employee, id) {
    const managerId = hierarchyManagerId(employee);
    if (managerId === id) brokenCycles.add(id);
    parent.set(id, managerId !== null && managerId !== id && byId.has(managerId) ? managerId : null);
  });

  // manager_id is a single-parent graph. Break each corrupt cycle at its
  // lowest numeric ID so rendering is deterministic and cannot recurse forever.
  const state = new Map();
  byId.forEach(function (_employee, startId) {
    if (state.get(startId) === 2) return;
    const path = [];
    const positions = new Map();
    let current = startId;
    while (current !== null && state.get(current) !== 2) {
      if (positions.has(current)) {
        const cycle = path.slice(positions.get(current));
        const breakId = Math.min.apply(null, cycle);
        parent.set(breakId, null);
        brokenCycles.add(breakId);
        break;
      }
      positions.set(current, path.length);
      path.push(current);
      state.set(current, 1);
      current = parent.get(current);
    }
    path.forEach(function (id) { state.set(id, 2); });
  });

  const children = new Map();
  parent.forEach(function (managerId, id) {
    if (managerId === null) return;
    if (!children.has(managerId)) children.set(managerId, []);
    children.get(managerId).push(id);
  });
  const sortIds = function (a, b) {
    return hierarchyName(byId.get(a)).localeCompare(hierarchyName(byId.get(b)));
  };
  children.forEach(function (ids) { ids.sort(sortIds); });
  const roots = Array.from(byId.keys()).filter(function (id) { return parent.get(id) === null; });
  roots.sort(sortIds);
  return { byId: byId, parent: parent, children: children, roots: roots, brokenCycles: brokenCycles };
}

function hierarchyInitials(employee) {
  return hierarchyName(employee).split(/\s+/).slice(0, 2)
    .map(function (part) { return part.charAt(0).toUpperCase(); }).join("");
}

function hierarchyPhoto(path) {
  if (typeof path !== "string" || !path.trim()) return "";
  const value = path.trim();
  if (value.startsWith("//") || value.includes("\\") || /^[a-z][a-z0-9+.-]*:/i.test(value)) return "";
  try {
    const url = new URL(value.startsWith("/") ? value : "/" + value, window.location.origin);
    return url.origin === window.location.origin ? url.href : "";
  } catch (_error) {
    return "";
  }
}

function hierarchyMatches(employee) {
  if (!hierarchyQuery) return true;
  const haystack = [hierarchyName(employee), employee.employee_code || ""]
    .join(" ").toLocaleLowerCase();
  return haystack.includes(hierarchyQuery);
}

function matchingSubtree(id, memo) {
  if (memo.has(id)) return memo.get(id);
  const matches = hierarchyMatches(hierarchyTree.byId.get(id)) ||
    (hierarchyTree.children.get(id) || []).some(function (childId) {
      return matchingSubtree(childId, memo);
    });
  memo.set(id, matches);
  return matches;
}

function buildQueryMemo() {
  const memo = new Map();
  hierarchyTree.roots.forEach(function (rootId) {
    const stack = [[rootId, false]];
    const visited = new Set();
    while (stack.length) {
      const frame = stack.pop();
      const id = frame[0];
      if (frame[1]) {
        const hasMatchingChild = (hierarchyTree.children.get(id) || []).some(function (childId) {
          return memo.get(childId) === true;
        });
        memo.set(id, hierarchyMatches(hierarchyTree.byId.get(id)) || hasMatchingChild);
      } else if (!visited.has(id)) {
        visited.add(id);
        stack.push([id, true]);
        (hierarchyTree.children.get(id) || []).forEach(function (childId) {
          if (!visited.has(childId)) stack.push([childId, false]);
        });
      }
    }
  });
  return memo;
}

function focusVisibleIds() {
  if (focusHierarchyId === null || !hierarchyTree.byId.has(focusHierarchyId)) return null;
  const visible = new Set();
  let current = focusHierarchyId;
  while (current !== null && !visible.has(current)) {
    visible.add(current);
    current = hierarchyTree.parent.get(current);
  }
  const stack = [focusHierarchyId];
  while (stack.length) {
    const id = stack.pop();
    (hierarchyTree.children.get(id) || []).forEach(function (childId) {
      if (!visible.has(childId)) {
        visible.add(childId);
        stack.push(childId);
      }
    });
  }
  return visible;
}

function hierarchyNode(id, depth, context) {
  if (depth > 100 || context.rendered.has(id)) return "";
  if (context.focusIds && !context.focusIds.has(id)) return "";
  if (context.queryMemo && !matchingSubtree(id, context.queryMemo)) return "";
  context.rendered.add(id);
  const employee = hierarchyTree.byId.get(id);
  const childIds = hierarchyTree.children.get(id) || [];
  const childHtml = childIds.map(function (childId) {
    return hierarchyNode(childId, depth + 1, context);
  }).join("");
  const hasChildren = childHtml !== "";
  const selected = selectedHierarchyId === id;
  const photo = hierarchyPhoto(employee.profile_photo_path);
  const name = hierarchyName(employee);
  const code = employee.employee_code || "ID unavailable";
  const designation = employee.designation_id
    ? "Designation ID " + employee.designation_id : "Designation unavailable";
  const department = employee.department_id
    ? "Department ID " + employee.department_id : "Department unavailable";
  const profileUrl = "/pages/employee-profile.html?id=" + id;
  const brokenCycle = hierarchyTree.brokenCycles.has(id)
    ? '<span class="org-cycle-note" title="The stored reporting cycle was cut at this record for display">Cycle corrected for display</span>'
    : "";
  const managerId = hierarchyTree.parent.get(id);
  const managerText = managerId === null
    ? (hierarchyManagerId(employee) !== null && !hierarchyTree.byId.has(hierarchyManagerId(employee))
      ? "Manager is outside your visible scope"
      : "Top of visible reporting scope")
    : "Reports to " + hierarchyName(hierarchyTree.byId.get(managerId));

  return '<li class="org-tree-item" data-org-item="' + id + '">' +
    '<article class="org-card' + (selected ? " is-selected" : "") + '" data-org-card="' + id + '" tabindex="0" aria-current="' + (selected ? "true" : "false") + '">' +
      '<button type="button" class="org-expand" data-org-toggle="' + id + '" aria-expanded="' + (hasChildren ? "true" : "false") + '" aria-label="' + (hasChildren ? "Collapse" : "No") + ' direct reports" ' + (!hasChildren ? "disabled" : "") + '>' +
        (hasChildren ? "-" : ".") +
      '</button>' +
      '<a class="org-avatar-link" href="' + profileUrl + '" aria-label="Open ' + escapeHtml(name) + ' profile">' +
        (photo ? '<img class="org-avatar" src="' + escapeHtml(photo) + '" alt="" loading="lazy" referrerpolicy="no-referrer">' : '<span class="org-avatar org-avatar-fallback" aria-hidden="true">' + escapeHtml(hierarchyInitials(employee)) + '</span>') +
      '</a>' +
      '<div class="org-card-main">' +
        '<a class="org-employee-name" href="' + profileUrl + '">' + escapeHtml(name) + '</a>' +
        '<span class="org-employee-code">' + escapeHtml(code) + '</span>' +
        '<span class="org-role-line">' + escapeHtml(designation) + ' <span aria-hidden="true">·</span> ' + escapeHtml(department) + '</span>' +
        '<span class="org-manager-line">' + escapeHtml(managerText) + '</span>' +
      '</div>' +
      '<span class="org-status org-status-' + escapeHtml(String(employee.employment_status || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-")) + '">' + escapeHtml(employee.employment_status || "Status unavailable") + '</span>' +
      brokenCycle +
      '<button type="button" class="org-focus-one" data-org-select="' + id + '" aria-label="Select ' + escapeHtml(name) + '">Select</button>' +
    '</article>' +
    (hasChildren ? '<ul class="org-tree-children">' + childHtml + '</ul>' : "") +
  '</li>';
}

function renderHierarchy() {
  const container = document.getElementById("hierarchy");
  const context = {
    rendered: new Set(),
    focusIds: focusVisibleIds(),
    queryMemo: hierarchyQuery ? buildQueryMemo() : null,
  };
  const html = hierarchyTree.roots.map(function (id) {
    return hierarchyNode(id, 1, context);
  }).join("");
  if (!html) {
    container.innerHTML = '<p class="empty">No employees match this search within your access scope.</p>';
  } else {
    container.innerHTML = '<ul class="org-tree">' + html + '</ul>';
  }
  const visibleRoots = hierarchyTree.roots.filter(function (id) {
    return context.rendered.has(id);
  }).length;
  const cycleCount = hierarchyTree.brokenCycles.size;
  document.getElementById("hierarchy-count").textContent =
    context.rendered.size + " visible employees · " + visibleRoots + " reporting branches" +
    (cycleCount ? " · " + cycleCount + " cycle" + (cycleCount === 1 ? "" : "s") + " safely corrected for display" : "");
}

function visibleDescendants(startId) {
  const found = [];
  const seen = new Set([startId]);
  const stack = (hierarchyTree.children.get(startId) || []).slice().reverse();
  while (stack.length) {
    const id = stack.pop();
    if (seen.has(id)) continue;
    seen.add(id);
    found.push(id);
    (hierarchyTree.children.get(id) || []).slice().reverse().forEach(function (childId) {
      stack.push(childId);
    });
  }
  return found;
}

function hierarchyProfileLink(id) {
  const employee = hierarchyTree.byId.get(id);
  return '<a href="/pages/employee-profile.html?id=' + id + '">' + escapeHtml(hierarchyName(employee)) + '</a>';
}

function renderSelectedSummary(id) {
  selectedHierarchyId = id;
  const summary = document.getElementById("selected-employee-summary");
  if (id === null || !hierarchyTree.byId.has(id)) {
    summary.hidden = true;
    summary.innerHTML = "";
    return;
  }
  const employee = hierarchyTree.byId.get(id);
  const chain = [];
  const seen = new Set();
  let managerId = hierarchyTree.parent.get(id);
  while (managerId !== null && !seen.has(managerId)) {
    seen.add(managerId);
    chain.unshift(managerId);
    managerId = hierarchyTree.parent.get(managerId);
  }
  const reports = visibleDescendants(id);
  const directReports = hierarchyTree.children.get(id) || [];
  summary.hidden = false;
  summary.innerHTML = '<div class="org-summary-heading"><div><p class="eyebrow">SELECTED EMPLOYEE</p><h2>' + escapeHtml(hierarchyName(employee)) + '</h2><span>' + escapeHtml(employee.employee_code || "ID unavailable") + '</span></div><a class="button secondary" href="/pages/employee-profile.html?id=' + id + '">Open Employee 360</a></div>' +
    '<div class="org-summary-columns">' +
      '<section><h3>Management chain</h3>' + (chain.length ? '<ol>' + chain.map(function (manager) { return '<li>' + hierarchyProfileLink(manager) + '</li>'; }).join("") + '<li class="org-chain-current">' + hierarchyProfileLink(id) + '</li>' : '<p class="muted">No manager is visible above this employee.</p>') + '</ol></section>' +
      '<section><h3>Reports <span>' + reports.length + '</span></h3><p class="muted">' + directReports.length + ' direct · ' + Math.max(0, reports.length - directReports.length) + ' indirect</p>' + (reports.length ? '<ul>' + reports.map(function (reportId) { return '<li>' + hierarchyProfileLink(reportId) + (hierarchyTree.parent.get(reportId) === id ? ' <span class="muted">Direct</span>' : '') + '</li>'; }).join("") + '</ul>' : '<p class="muted">No reports in your visible scope.</p>') + '</section>' +
    '</div>';
  renderHierarchy();
}

function populateFocusSelect() {
  const select = document.getElementById("hierarchy-focus");
  const entries = Array.from(hierarchyTree.byId.entries()).sort(function (a, b) {
    return hierarchyName(a[1]).localeCompare(hierarchyName(b[1]));
  });
  select.innerHTML = '<option value="">Select an employee</option>' + entries.map(function (entry) {
    const id = entry[0];
    const employee = entry[1];
    return '<option value="' + id + '">' + escapeHtml(hierarchyName(employee)) + ' · ' + escapeHtml(employee.employee_code || "ID unavailable") + '</option>';
  }).join("");
  ["hierarchy-focus", "focus-button", "show-all-button", "expand-all-button", "collapse-all-button"]
    .forEach(function (id) { document.getElementById(id).disabled = false; });
}

function wireHierarchyControls() {
  const search = document.getElementById("hierarchy-search");
  const select = document.getElementById("hierarchy-focus");
  search.addEventListener("input", function () {
    hierarchyQuery = search.value.trim().toLocaleLowerCase();
    renderHierarchy();
  });
  document.getElementById("focus-button").addEventListener("click", function () {
    focusHierarchyId = select.value ? Number(select.value) : null;
    if (focusHierarchyId !== null) renderSelectedSummary(focusHierarchyId);
    renderHierarchy();
  });
  document.getElementById("show-all-button").addEventListener("click", function () {
    focusHierarchyId = null;
    hierarchyQuery = "";
    search.value = "";
    select.value = "";
    renderHierarchy();
  });
  document.getElementById("expand-all-button").addEventListener("click", function () {
    document.querySelectorAll(".org-tree-children").forEach(function (list) { list.hidden = false; });
    document.querySelectorAll(".org-expand:not(:disabled)").forEach(function (button) {
      button.setAttribute("aria-expanded", "true");
      button.textContent = "-";
    });
  });
  document.getElementById("collapse-all-button").addEventListener("click", function () {
    document.querySelectorAll(".org-tree-children").forEach(function (list) { list.hidden = true; });
    document.querySelectorAll(".org-expand:not(:disabled)").forEach(function (button) {
      button.setAttribute("aria-expanded", "false");
      button.textContent = "+";
    });
  });
  const container = document.getElementById("hierarchy");
  container.addEventListener("click", function (event) {
    if (event.target.closest("a")) return;
    const toggle = event.target.closest("[data-org-toggle]");
    if (toggle) {
      const item = toggle.closest(".org-tree-item");
      const list = item ? item.querySelector(":scope > .org-tree-children") : null;
      if (!list) return;
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      toggle.textContent = expanded ? "+" : "-";
      list.hidden = expanded;
      return;
    }
    const selectButton = event.target.closest("[data-org-select]");
    const card = event.target.closest("[data-org-card]");
    const id = selectButton ? Number(selectButton.dataset.orgSelect) : card ? Number(card.dataset.orgCard) : null;
    if (id !== null && hierarchyTree.byId.has(id)) {
      select.value = String(id);
      renderSelectedSummary(id);
    }
  });
  container.addEventListener("keydown", function (event) {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-org-card]")) {
      event.preventDefault();
      const id = Number(event.target.dataset.orgCard);
      select.value = String(id);
      renderSelectedSummary(id);
    }
  });
}

(async function initHierarchy() {
  const user = await requireAuth();
  if (!user) return;
  initShell(user, "hierarchy");
  showFlash();
  if (!canRead(user)) {
    document.getElementById("hierarchy").innerHTML = '<p class="empty">No employee hierarchy is available for your role.</p>';
    document.getElementById("hierarchy-count").textContent = "Employee access is not available.";
    showMessage("error", "Your role does not grant access to employee records.");
    return;
  }
  const result = await apiGet("/api/employees");
  if (!handleApiResult(result)) return;
  hierarchyEmployees = Array.isArray(result.data.employees) ? result.data.employees : [];
  if (!hierarchyEmployees.length) {
    document.getElementById("hierarchy").innerHTML = '<p class="empty">No employees found for your access level.</p>';
    document.getElementById("hierarchy-count").textContent = "No visible employee records.";
    return;
  }
  hierarchyTree = buildHierarchy(hierarchyEmployees);
  wireHierarchyControls();
  populateFocusSelect();
  document.getElementById("hierarchy-scope-note").hidden = false;
  document.getElementById("hierarchy-scope-note").textContent =
    "Reporting branches are built from actual manager records visible to your role. A top card may mark the edge of your authorized scope rather than the organization head.";
  renderHierarchy();
})();
