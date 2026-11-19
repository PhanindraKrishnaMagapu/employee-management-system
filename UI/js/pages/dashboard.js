// Dashboard metrics are calculated only from role-scoped existing API data.

function setDashboardCount(id, value) {
  document.getElementById(id).textContent = String(value);
}

function formatDashboardDate(value) {
  if (!value) {
    return "Not available";
  }
  const parts = String(value).slice(0, 10).split("-");
  return parts.length === 3 ? parts[1] + "/" + parts[2] + "/" + parts[0] : String(value);
}

function setDashboardDate() {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const element = document.getElementById("dashboard-date");
  element.dateTime = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
  element.textContent = formatter.format(now);
}

function visibleEmployeesByRecentJoining(employees) {
  return employees.slice().sort(function (left, right) {
    return String(right.joining_date || "").localeCompare(String(left.joining_date || ""));
  });
}

function departmentLabel(departmentId) {
  return departmentId === null || departmentId === undefined
    ? "Department not assigned"
    : "Department ID " + departmentId;
}

function renderDistribution(container, entries, total, emptyMessage) {
  if (total === 0 || entries.length === 0) {
    container.innerHTML = '<p class="dashboard-empty-inline">' + escapeHtml(emptyMessage) + "</p>";
    return;
  }

  container.innerHTML = entries
    .map(function (entry) {
      const percentage = total ? Math.round((entry.count / total) * 100) : 0;
      return (
        '<div class="dashboard-chart-row">' +
          '<div class="dashboard-chart-label"><span>' + escapeHtml(entry.label) +
          '</span><strong>' + entry.count + "</strong></div>" +
          '<div class="dashboard-chart-track" role="progressbar" aria-label="' +
          escapeHtml(entry.label + ": " + entry.count + " of " + total + " employees") +
          '" aria-valuemin="0" aria-valuemax="' + total + '" aria-valuenow="' + entry.count + '">' +
            '<span class="dashboard-chart-fill ' + escapeHtml(entry.color || "") + '" style="width:' + percentage + '%"></span>' +
          "</div>" +
        "</div>"
      );
    })
    .join("");
}

function renderEmployeeCharts(employees) {
  const departmentCounts = new Map();
  employees.forEach(function (employee) {
    if (employee.department_id === null || employee.department_id === undefined) {
      return;
    }
    const key = String(employee.department_id);
    departmentCounts.set(key, (departmentCounts.get(key) || 0) + 1);
  });

  const departments = Array.from(departmentCounts.entries())
    .sort(function (left, right) { return left[0].localeCompare(right[0], undefined, { numeric: true }); })
    .map(function (entry) {
      return { label: "Department ID " + entry[0], count: entry[1], color: "fill-blue" };
    });
  renderDistribution(
    document.getElementById("department-chart"),
    departments,
    employees.length,
    "No department data is available in your view."
  );

  const statusLabels = [
    { label: "Active", color: "fill-green" },
    { label: "Pre-joining", color: "fill-amber" },
    { label: "Exited", color: "fill-slate" },
  ];
  const statuses = statusLabels.map(function (status) {
    return {
      label: status.label,
      count: employees.filter(function (employee) {
        return employee.employment_status === status.label;
      }).length,
      color: status.color,
    };
  });
  renderDistribution(
    document.getElementById("status-chart"),
    statuses,
    employees.length,
    "No employee status data is available in your view."
  );
}

function renderRecentEmployees(employees) {
  const rows = visibleEmployeesByRecentJoining(employees).slice(0, 5);
  document.getElementById("recent-employee-rows").innerHTML = rows
    .map(function (employee) {
      const name = [employee.first_name, employee.last_name].filter(Boolean).join(" ");
      return (
        "<tr>" +
          "<td>" + escapeHtml(name || "Not available") + "</td>" +
          "<td>" + escapeHtml(employee.employee_code || "Not available") + "</td>" +
          "<td>" + escapeHtml(departmentLabel(employee.department_id)) + "</td>" +
          '<td><span class="dashboard-status status-' +
            escapeHtml(String(employee.employment_status || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-")) +
          '">' + escapeHtml(employee.employment_status || "Not available") + "</span></td>" +
        "</tr>"
      );
    })
    .join("");
  document.getElementById("recent-employees-empty").hidden = rows.length > 0;
}

function renderRecentJml(events) {
  const recent = events.slice(0, 5);
  const list = document.getElementById("recent-activity-list");
  list.innerHTML = recent
    .map(function (event) {
      const employee = event.employee || {};
      const name = [employee.first_name, employee.last_name].filter(Boolean).join(" ");
      const subject = name || employee.employee_code || "Employee record";
      const date = formatDashboardDate(event.created_at || event.effective_date);
      return (
        '<li class="dashboard-activity-item">' +
          '<span class="dashboard-activity-marker" aria-hidden="true"></span>' +
          '<div class="dashboard-activity-copy"><strong>' +
            escapeHtml(event.event_type || "JML event") + " · " + escapeHtml(subject) +
          '</strong><span>' + escapeHtml(event.status || "Status unavailable") +
            " · " + escapeHtml(date) + "</span></div>" +
        "</li>"
      );
    })
    .join("");
  document.getElementById("recent-activity-empty").hidden = recent.length > 0;
}

function configureQuickActions(user) {
  const visibility = [
    ["view-employees-action", canRead(user)],
    ["view-link", canRead(user)],
    ["hierarchy-link", canRead(user)],
    ["projects-link", canReadProjects(user)],
    ["skills-link", canReadSkills(user)],
    ["jml-action-link", canReadJml(user)],
    ["jml-link", canReadJml(user)],
    ["salary-link", canReadSalary(user)],
    ["add-link", canCreate(user)],
  ];
  visibility.forEach(function (item) {
    const element = document.getElementById(item[0]);
    if (element) {
      element.hidden = !item[1];
    }
  });
}

(async function initDashboard() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "dashboard");
  showFlash();
  setDashboardDate();
  configureQuickActions(user);

  let welcomeName = user.username || "there";
  // The profile endpoint resolves the authenticated user's linked employee
  // without a client-supplied ID. Skip it for salary-authorized roles because
  // that endpoint also returns compensation to those roles.
  if (!canReadSalary(user)) {
    const profileResult = await apiGet("/api/profile");
    if (profileResult.status === 401) {
      handleApiResult(profileResult);
      return;
    }
    if (profileResult.ok && profileResult.data.employee) {
      const employee = profileResult.data.employee;
      const fullName = [employee.first_name, employee.last_name]
        .filter(Boolean)
        .join(" ");
      welcomeName = fullName || welcomeName;
    }
  }
  document.getElementById("welcome-name").textContent = welcomeName;

  const canViewEmployees = canRead(user);
  const canViewJml = canReadJml(user);
  const otherAccess = [];
  if (canReadProjects(user)) otherAccess.push("projects");
  if (canReadSkills(user)) otherAccess.push("skills");
  if (canReadSalary(user)) otherAccess.push("salary");

  if (!canViewEmployees) {
    document.getElementById("no-employee-access").hidden = false;
    if (otherAccess.length === 0 && !canViewJml) {
      showMessage("error", "Your role does not grant access to employee records, projects, skills, salary, or JML events.");
    }
  } else {
    const accessLevel = can(user, "readAll") ? "All employees" : "Assigned scope";
    document.getElementById("access-level").textContent = accessLevel;
    document.getElementById("employee-dashboard").hidden = false;

    const employeeResult = await apiGet("/api/employees");
    if (!handleApiResult(employeeResult)) {
      return;
    }
    const employees = employeeResult.data.employees || [];
    const activeCount = employees.filter(function (employee) {
      return employee.employment_status === "Active";
    }).length;
    const departmentIds = new Set(employees
      .filter(function (employee) { return employee.department_id !== null && employee.department_id !== undefined; })
      .map(function (employee) { return String(employee.department_id); }));

    setDashboardCount("total-employees", employees.length);
    setDashboardCount("active-employees", activeCount);
    setDashboardCount("inactive-employees", employees.length - activeCount);
    setDashboardCount("total-departments", departmentIds.size);
    renderEmployeeCharts(employees);
    renderRecentEmployees(employees);
  }

  if (canViewJml) {
    const jmlResult = await apiGet("/api/jml/events");
    if (!handleApiResult(jmlResult)) {
      return;
    }
    const events = jmlResult.data.events || [];
    const pendingCount = events.filter(function (event) {
      return event.status === "Pending";
    }).length;
    document.getElementById("pending-jml-events").textContent = String(pendingCount);
    document.getElementById("pending-jml-kpi").hidden = false;
    document.getElementById("recent-activity-section").hidden = false;
    renderRecentJml(events);
  }
})();
