// Employee hierarchy: reporting tree built from the scoped employee list.
// Uses GET /api/employees, so the backend already applied RBAC and record scope.

const MAX_TREE_DEPTH = 25;

function _managerIdOf(employee) {
  if (employee.manager_id === null || employee.manager_id === undefined) {
    return null;
  }
  const id = Number(employee.manager_id);
  return Number.isNaN(id) ? null : id;
}

function buildHierarchy(employees) {
  const byId = new Map();
  employees.forEach(function (employee) {
    const id = Number(employee.id);
    if (!Number.isNaN(id)) {
      byId.set(id, employee);
    }
  });

  const children = new Map();
  byId.forEach(function (employee, id) {
    const managerId = _managerIdOf(employee);
    if (managerId !== null && managerId !== id && byId.has(managerId)) {
      if (!children.has(managerId)) {
        children.set(managerId, []);
      }
      children.get(managerId).push(id);
    }
  });

  const roots = [];
  const reachable = new Set();

  function markReachable(startId) {
    const stack = [startId];
    const seen = new Set();
    while (stack.length > 0) {
      const id = stack.pop();
      if (seen.has(id) || !byId.has(id)) {
        continue;
      }
      seen.add(id);
      reachable.add(id);
      (children.get(id) || []).forEach(function (childId) {
        stack.push(childId);
      });
    }
  }

  // Top-level employees have no visible manager. A manager outside the user's
  // scope is also treated as absent, so their reports become roots.
  byId.forEach(function (employee, id) {
    const managerId = _managerIdOf(employee);
    if (managerId === null || managerId === id || !byId.has(managerId)) {
      roots.push(id);
      markReachable(id);
    }
  });

  // Cyclic manager chains have no natural root; expose one so nothing is lost.
  byId.forEach(function (employee, id) {
    if (!reachable.has(id)) {
      roots.push(id);
      markReachable(id);
    }
  });

  function byIdSort(a, b) {
    return a - b;
  }
  roots.sort(byIdSort);
  children.forEach(function (list) {
    list.sort(byIdSort);
  });

  return { byId: byId, children: children, roots: roots };
}

function renderNode(id, tree, depth, shown) {
  if (depth > MAX_TREE_DEPTH || shown.has(id)) {
    return "";
  }

  const employee = tree.byId.get(id);
  if (!employee) {
    return "";
  }
  shown.add(id);

  const nameParts = [employee.first_name, employee.last_name].filter(function (part) {
    return part !== null && part !== undefined && String(part).trim() !== "";
  });
  const name = escapeHtml(nameParts.join(" ") || employee.employee_code);
  const code = escapeHtml(employee.employee_code);
  const status = escapeHtml(employee.employment_status);

  const childHtml = (tree.children.get(id) || [])
    .map(function (childId) {
      return renderNode(childId, tree, depth + 1, shown);
    })
    .join("");
  const hasChildren = childHtml !== "";

  const toggle = hasChildren
    ? '<button type="button" class="tree-toggle" aria-expanded="true" aria-label="Collapse reporting level">▾</button>'
    : '<span class="tree-spacer" aria-hidden="true"></span>';

  return (
    '<li class="tree-item">' +
      '<div class="tree-node" data-node-id="' + Number(id) + '">' +
        toggle +
        '<span class="tree-label">' + name + '</span>' +
        '<span class="tree-meta">' + code + '</span>' +
        '<span class="tree-status">' + status + '</span>' +
      '</div>' +
      (hasChildren ? '<ul class="tree-children">' + childHtml + '</ul>' : '') +
    '</li>'
  );
}

function renderHierarchy(employees) {
  const container = document.getElementById("hierarchy");
  const tree = buildHierarchy(employees);
  const shown = new Set();
  const itemHtml = tree.roots
    .map(function (rootId) {
      return renderNode(rootId, tree, 1, shown);
    })
    .join("");

  if (itemHtml === "") {
    container.innerHTML = '<p class="empty">No employees found for your access level.</p>';
    return;
  }

  container.innerHTML = '<ul class="tree">' + itemHtml + '</ul>';
}

function wireTreeToggles() {
  const container = document.getElementById("hierarchy");
  container.addEventListener("click", function (event) {
    const button = event.target.closest(".tree-toggle");
    if (!button) {
      return;
    }

    const item = button.closest(".tree-item");
    const children = item ? item.querySelector(":scope > .tree-children") : null;
    if (!children) {
      return;
    }

    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", expanded ? "false" : "true");
    button.textContent = expanded ? "▸" : "▾";
    button.setAttribute(
      "aria-label",
      expanded ? "Expand reporting level" : "Collapse reporting level"
    );
    children.hidden = expanded;
  });
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "hierarchy");
  showFlash();
  wireTreeToggles();

  if (!canRead(user)) {
    document.getElementById("hierarchy").innerHTML =
      '<p class="empty">No employee hierarchy is available for your role.</p>';
    showMessage("error", "Your role does not grant access to employee records.");
    return;
  }

  const result = await apiGet("/api/employees");
  if (!handleApiResult(result)) {
    return;
  }

  const employees = Array.isArray(result.data.employees)
    ? result.data.employees
    : [];
  if (employees.length === 0) {
    document.getElementById("hierarchy").innerHTML =
      '<p class="empty">No employees found for your access level.</p>';
    return;
  }

  renderHierarchy(employees);
})();
