// Employee 360 view: every section is loaded through the existing scoped API.

const PROFILE_TREE_MAX_DEPTH = 6;
const PROFILE_TREE_MAX_NODES = 100;
let profilePageUser = null;
let profileEmployee = null;

function profileText(value) {
  return value === null || value === undefined || String(value).trim() === ""
    ? "Not available"
    : String(value);
}

function profileDate(value) {
  if (!value) {
    return "Not available";
  }
  const parts = String(value).slice(0, 10).split("-");
  return parts.length === 3 ? parts[1] + "/" + parts[2] + "/" + parts[0] : String(value);
}

function employeeFullName(employee) {
  return [employee.first_name, employee.last_name]
    .filter(function (value) { return value !== null && value !== undefined && String(value).trim(); })
    .join(" ") || employee.employee_code || "Employee";
}

function safeProfilePhoto(path) {
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

function setProfileValue(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = profileText(value);
  }
}

function setProfileImage(employee) {
  const avatar = document.getElementById("employee-avatar");
  const name = employeeFullName(employee);
  avatar.textContent = name.charAt(0).toUpperCase();
  const photo = safeProfilePhoto(employee.profile_photo_path);
  if (photo) {
    const image = document.createElement("img");
    image.src = photo;
    image.alt = "";
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", function () { image.remove(); });
    avatar.appendChild(image);
  }
}

function renderEmployeeHeader(employee) {
  const name = employeeFullName(employee);
  document.getElementById("employee-name").textContent = name;
  document.title = name + " · Employee 360";
  setProfileImage(employee);

  const statusClass = String(employee.employment_status || "unknown")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const metadata = [
    employee.employee_code || "Employee ID unavailable",
    employee.designation_id ? "Designation ID " + employee.designation_id : "Designation unavailable",
    employee.department_id ? "Department ID " + employee.department_id : "Department unavailable",
  ];
  document.getElementById("employee-meta").innerHTML =
    '<span>' + escapeHtml(metadata.join(" · ")) + '</span>' +
    '<span class="e360-status status-' + escapeHtml(statusClass) + '">' +
      escapeHtml(employee.employment_status || "Not available") + "</span>";

  const actions = [];
  if (canEdit(profilePageUser)) {
    actions.push('<a class="button primary" href="/pages/employee-form.html?id=' +
      Number(employee.id) + '">Edit employee</a>');
  }
  document.getElementById("employee-hero-actions").innerHTML = actions.join("");
}

function renderEmployeeBasics(employee) {
  const name = employeeFullName(employee);
  const department = employee.department_id === null || employee.department_id === undefined
    ? "Not available"
    : "Department ID " + employee.department_id;
  const designation = employee.designation_id === null || employee.designation_id === undefined
    ? "Not available"
    : "Designation ID " + employee.designation_id;
  const manager = employee.manager_id === null || employee.manager_id === undefined
    ? "Not available"
    : "Manager record is outside the available profile data";

  setProfileValue("overview-code", employee.employee_code);
  setProfileValue("overview-designation", designation);
  setProfileValue("overview-department", department);
  setProfileValue("overview-status", employee.employment_status);
  setProfileValue("personal-name", name);
  setProfileValue("personal-email", employee.official_email);
  setProfileValue("personal-phone", employee.phone);
  setProfileValue("personal-dob", employee.date_of_birth);
  setProfileValue("personal-location", employee.location);
  setProfileValue("employment-designation", designation);
  setProfileValue("employment-department", department);
  setProfileValue("employment-joining-date", profileDate(employee.joining_date));
  setProfileValue("employment-type", employee.employment_type);
  setProfileValue("employment-manager", manager);
  setProfileValue("employment-status", employee.employment_status);
  setProfileValue("employment-location", employee.location);
}

function renderTabs() {
  document.querySelectorAll("#employee-profile-tabs [data-section]").forEach(function (tab) {
    const section = document.getElementById(tab.getAttribute("data-section"));
    tab.hidden = !section || section.hidden;
  });
  const tabs = document.querySelectorAll("#employee-profile-tabs a");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (other) { other.classList.remove("active"); });
      tab.classList.add("active");
    });
  });
  const overview = document.querySelector('#employee-profile-tabs a[href="#overview"]');
  if (overview) overview.classList.add("active");
}

function renderStatusBadge(value) {
  const statusClass = String(value || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return '<span class="e360-status status-' + escapeHtml(statusClass) + '">' +
    escapeHtml(value || "Not available") + "</span>";
}

async function loadEmployeeSkills(employeeId) {
  if (!canReadSkills(profilePageUser)) {
    return;
  }
  const section = document.getElementById("skills-section");
  section.hidden = false;
  const result = await apiGet("/api/employees/" + employeeId + "/skills");
  if (!handleOptionalResult(result)) {
    section.hidden = true;
    return;
  }
  const assignments = Array.isArray(result.data.assignments) ? result.data.assignments : [];
  document.getElementById("skill-record-rows").innerHTML = assignments.map(function (assignment) {
    const skill = assignment.skill || {};
    return (
      "<tr>" +
        "<td><strong>" + escapeHtml(skill.name || "Not available") +
          (skill.description ? '<span class="e360-subcell">' + escapeHtml(skill.description) + "</span>" : "") + "</td>" +
        "<td>" + escapeHtml(assignment.proficiency_level || "Not available") + "</td>" +
        "<td>" + escapeHtml(assignment.experience_years === null || assignment.experience_years === undefined
          ? "Not available"
          : String(assignment.experience_years) + " years") + "</td>" +
        "<td>" + escapeHtml(profileDate(assignment.last_verified)) + "</td>" +
      "</tr>"
    );
  }).join("");
  document.getElementById("skills-empty").hidden = assignments.length > 0;
}

function formatSalary(value, currency) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "Not available";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "INR",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch (error) {
    return amount.toLocaleString() + (currency ? " " + currency : "");
  }
}

async function loadEmployeeSalary(employeeId) {
  if (!canReadSalary(profilePageUser)) {
    return;
  }
  const section = document.getElementById("salary-section");
  section.hidden = false;
  const salaries = [];
  let offset = 0;
  let total = 0;
  do {
    const result = await apiGet(
      "/api/salaries?employee_id=" + encodeURIComponent(employeeId) +
      "&limit=500&offset=" + offset
    );
    if (!handleOptionalResult(result)) {
      section.hidden = true;
      return;
    }
    (result.data.salaries || []).forEach(function (salary) {
      if (Number(salary.employee_id) === employeeId) salaries.push(salary);
    });
    total = Number(result.data.total) || 0;
    offset += Number(result.data.limit) || 500;
  } while (offset < total);

  const today = new Date();
  const todayValue = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");
  const currentSalary = salaries.find(function (salary) {
    return salary.effective_from <= todayValue &&
      (!salary.effective_to || salary.effective_to >= todayValue);
  });
  setProfileValue(
    "current-salary-value",
    currentSalary
      ? formatSalary(currentSalary.annual_salary, currentSalary.currency)
      : "No current salary record"
  );
  [
    ["current-monthly-gross", "monthly_gross_salary"],
    ["current-monthly-basic", "monthly_basic_salary"],
    ["current-monthly-hra", "monthly_hra"],
    ["current-monthly-allowances", "monthly_allowances"],
    ["current-monthly-deductions", "monthly_deductions"],
  ].forEach(function (item) {
    setProfileValue(
      item[0],
      currentSalary && currentSalary[item[1]] !== null && currentSalary[item[1]] !== undefined
        ? formatSalary(currentSalary[item[1]], currentSalary.currency)
        : "Not available"
    );
  });
  setProfileValue(
    "current-salary-effective",
    currentSalary ? profileDate(currentSalary.effective_from) : "Not available"
  );

  const addSalaryLink = document.getElementById("salary-add-link");
  if (canManageSalary(profilePageUser)) {
    addSalaryLink.href = "/pages/salary-form.html?employee_id=" + encodeURIComponent(employeeId);
    addSalaryLink.hidden = false;
  }

  document.getElementById("salary-record-rows").innerHTML = salaries.map(function (salary) {
    const editLink = canManageSalary(profilePageUser)
      ? '<a href="/pages/salary-form.html?id=' + Number(salary.id) + '">Edit</a>'
      : "";
    return (
      "<tr>" +
        "<td>" + escapeHtml(formatSalary(salary.annual_salary, salary.currency)) + "</td>" +
        "<td>" + escapeHtml(salary.monthly_gross_salary == null ? "Not available" : formatSalary(salary.monthly_gross_salary, salary.currency)) + "</td>" +
        "<td>" + escapeHtml(salary.monthly_basic_salary == null ? "Not available" : formatSalary(salary.monthly_basic_salary, salary.currency)) + "</td>" +
        "<td>" + escapeHtml(salary.monthly_hra == null ? "Not available" : formatSalary(salary.monthly_hra, salary.currency)) + "</td>" +
        "<td>" + escapeHtml(salary.monthly_allowances == null ? "Not available" : formatSalary(salary.monthly_allowances, salary.currency)) + "</td>" +
        "<td>" + escapeHtml(salary.monthly_deductions == null ? "Not available" : formatSalary(salary.monthly_deductions, salary.currency)) + "</td>" +
        "<td>" + escapeHtml(profileDate(salary.effective_from)) + "</td>" +
        "<td>" + escapeHtml(profileDate(salary.effective_to)) + "</td>" +
        "<td>" + editLink + "</td>" +
      "</tr>"
    );
  }).join("");
  document.getElementById("salary-empty").hidden = salaries.length > 0;
}

function employeeLink(employee) {
  const id = Number(employee.id);
  return '<a href="/pages/employee-profile.html?id=' + id + '">' +
    escapeHtml(employeeFullName(employee)) + " · " + escapeHtml(employee.employee_code || "") + "</a>";
}

function renderHierarchy(employees, employee) {
  const byId = new Map();
  employees.forEach(function (item) {
    const id = Number(item.id);
    if (Number.isInteger(id)) byId.set(id, item);
  });
  const employeeId = Number(employee.id);
  const chain = [];
  const seen = new Set([employeeId]);
  let current = employee;
  let hiddenManager = false;
  while (current.manager_id !== null && current.manager_id !== undefined) {
    const managerId = Number(current.manager_id);
    if (seen.has(managerId)) break;
    const manager = byId.get(managerId);
    if (!manager) {
      hiddenManager = true;
      break;
    }
    seen.add(managerId);
    chain.push(manager);
    current = manager;
  }
  chain.reverse();
  const chainList = document.getElementById("manager-chain");
  chainList.innerHTML = chain.map(function (manager) {
    return "<li>" + employeeLink(manager) + "</li>";
  }).join("");
  if (hiddenManager && chain.length === 0) {
    chainList.innerHTML = "<li>Reporting manager is outside your visible employee scope.</li>";
  } else if (!chain.length) {
    chainList.innerHTML = "<li>No reporting manager recorded.</li>";
  }

  const children = new Map();
  byId.forEach(function (item, id) {
    if (item.manager_id === null || item.manager_id === undefined) return;
    const managerId = Number(item.manager_id);
    if (!children.has(managerId)) children.set(managerId, []);
    children.get(managerId).push(id);
  });
  children.forEach(function (ids) {
    ids.sort(function (left, right) {
      return employeeFullName(byId.get(left)).localeCompare(employeeFullName(byId.get(right)));
    });
  });

  const reports = (children.get(employeeId) || []).map(function (id) { return byId.get(id); });
  const reportsList = document.getElementById("direct-reports");
  reportsList.innerHTML = reports.map(function (report) {
    return "<li>" + employeeLink(report) + "</li>";
  }).join("");
  if (!reports.length) reportsList.innerHTML = "<li>No direct reports in your visible scope.</li>";

  let nodeBudget = PROFILE_TREE_MAX_NODES;
  let truncated = false;
  function renderTreeNode(item, depth, path) {
    if (nodeBudget <= 0) {
      truncated = true;
      return "";
    }
    nodeBudget -= 1;
    const id = Number(item.id);
    const name = employeeLink(item) + " " + renderStatusBadge(item.employment_status);
    const nextPath = new Set(path);
    nextPath.add(id);
    let descendants = "";
    if (depth < PROFILE_TREE_MAX_DEPTH) {
      const childItems = (children.get(id) || []).filter(function (childId) {
        return !nextPath.has(childId);
      });
      if (childItems.length) {
        descendants = "<ul>" + childItems.map(function (childId) {
          return renderTreeNode(byId.get(childId), depth + 1, nextPath);
        }).join("") + "</ul>";
      }
    } else if ((children.get(id) || []).some(function (childId) { return !nextPath.has(childId); })) {
      truncated = true;
    }
    return "<li>" + name + descendants + "</li>";
  }
  document.getElementById("employee-reporting-tree").innerHTML =
    "<ul>" + renderTreeNode(employee, 0, new Set()) + "</ul>";
  if (truncated) {
    document.getElementById("employee-reporting-tree").insertAdjacentHTML(
      "beforeend",
      '<p class="e360-tree-limit">Showing the first ' + PROFILE_TREE_MAX_NODES +
        " employees and up to " + PROFILE_TREE_MAX_DEPTH +
        ' reporting levels. Open the hierarchy page for the full visible tree.</p>'
    );
  }
}

async function loadHierarchy(employee) {
  const result = await apiGet("/api/employees");
  if (!handleOptionalResult(result)) {
    return;
  }
  const employees = Array.isArray(result.data.employees) ? result.data.employees : [];
  renderHierarchy(employees, employee);
}

async function loadEmployeeProjects(employeeId) {
  if (!canReadProjects(profilePageUser)) {
    return;
  }
  const section = document.getElementById("projects-section");
  section.hidden = false;
  const result = await apiGet("/api/projects");
  if (!handleOptionalResult(result)) {
    section.hidden = true;
    return;
  }
  const projects = Array.isArray(result.data.projects) ? result.data.projects : [];
  const assignments = [];
  for (const project of projects) {
    const assignmentResult = await apiGet("/api/projects/" + Number(project.id) + "/employees");
    if (assignmentResult.status === 401) {
      handleApiResult(assignmentResult);
      section.hidden = true;
      return;
    }
    if (assignmentResult.status === 403 || assignmentResult.status === 404) {
      showMessage("error", "Project assignments are unavailable for this employee profile.");
      section.hidden = true;
      return;
    }
    if (!assignmentResult.ok) {
      handleApiResult(assignmentResult);
      section.hidden = true;
      return;
    }
    (assignmentResult.data.assignments || []).forEach(function (assignment) {
      if (Number(assignment.employee_id) === employeeId) {
        assignments.push({ project: project, assignment: assignment });
      }
    });
  }

  document.getElementById("project-record-rows").innerHTML = assignments.map(function (item) {
    const project = item.project;
    const assignment = item.assignment;
    return (
      "<tr>" +
        '<td><a href="/pages/project-detail.html?id=' + Number(project.id) + '">' + escapeHtml(project.name) + "</a></td>" +
        "<td>" + escapeHtml(project.status || "Not available") + "</td>" +
        "<td>" + escapeHtml(assignment.allocation_percentage === null || assignment.allocation_percentage === undefined
          ? "Not available"
          : String(assignment.allocation_percentage) + "%") + "</td>" +
        "<td>" + escapeHtml(profileDate(assignment.start_date)) + "</td>" +
        "<td>" + escapeHtml(profileDate(assignment.end_date)) + "</td>" +
      "</tr>"
    );
  }).join("");
  document.getElementById("projects-empty").hidden = assignments.length > 0;
}

function renderJmlEvents(events, employeeId) {
  const related = events.filter(function (event) {
    return Number(event.employee_id) === employeeId;
  });
  document.getElementById("jml-record-rows").innerHTML = related.map(function (event) {
    return (
      "<tr>" +
        "<td>" + escapeHtml(event.event_type || "Not available") + "</td>" +
        "<td>" + renderStatusBadge(event.status) + "</td>" +
        "<td>" + escapeHtml(profileDate(event.effective_date)) + "</td>" +
        "<td>" + escapeHtml(profileDate(event.created_at)) + "</td>" +
      "</tr>"
    );
  }).join("");
  document.getElementById("jml-empty").hidden = related.length > 0;
  return related;
}

function historyChanges(record) {
  const changes = [
    ["Department ID", record.old_department_id, record.new_department_id],
    ["Designation ID", record.old_designation_id, record.new_designation_id],
    ["Manager ID", record.old_manager_id, record.new_manager_id],
    ["Location", record.old_location, record.new_location],
  ].filter(function (item) {
    return item[1] !== item[2];
  });
  return changes.map(function (item) {
    return item[0] + ": " + profileText(item[1]) + " → " + profileText(item[2]);
  }).join(" · ") || "Employee reporting or assignment history recorded";
}

async function loadEmployeeJmlAndActivity(employeeId) {
  if (!canReadJml(profilePageUser)) {
    return;
  }
  document.getElementById("jml-section").hidden = false;
  document.getElementById("activity-section").hidden = false;
  const result = await apiGet("/api/jml/events");
  if (!handleOptionalResult(result)) {
    document.getElementById("jml-section").hidden = true;
    document.getElementById("activity-section").hidden = true;
    return;
  }
  const events = Array.isArray(result.data.events) ? result.data.events : [];
  const related = renderJmlEvents(events, employeeId);
  const mover = related.find(function (event) { return event.event_type === "Mover"; });
  if (!mover) {
    document.getElementById("activity-empty").hidden = false;
    return;
  }
  const detailResult = await apiGet("/api/jml/events/" + Number(mover.id));
  if (!handleOptionalResult(detailResult)) {
    document.getElementById("activity-section").hidden = true;
    return;
  }
  const history = Array.isArray(detailResult.data.history) ? detailResult.data.history : [];
  document.getElementById("activity-records").innerHTML = history.map(function (record) {
    return (
      "<li><time>" + escapeHtml(profileDate(record.effective_date)) +
      "</time><span>" + escapeHtml(historyChanges(record)) + "</span></li>"
    );
  }).join("");
  document.getElementById("activity-empty").hidden = history.length > 0;
}

function handleOptionalResult(result) {
  if (result.status === 401) {
    return handleApiResult(result);
  }
  if (result.status === 403 || result.status === 404) {
    showMessage("error", "Some profile information is unavailable for your account.");
    return false;
  }
  return handleApiResult(result);
}

(async function initEmployeeProfile() {
  const user = await requireAuth();
  if (!user) {
    return;
  }
  profilePageUser = user;
  initShell(user, "employees");
  showFlash();

  if (!canRead(user)) {
    showMessage("error", "Your role does not grant access to employee profiles.");
    return;
  }

  const rawId = new URLSearchParams(window.location.search).get("id") || "";
  if (!/^[1-9]\d*$/.test(rawId)) {
    showMessage("error", "This employee profile is unavailable for your account.");
    return;
  }
  const employeeId = Number(rawId);
  if (!Number.isSafeInteger(employeeId)) {
    showMessage("error", "This employee profile is unavailable for your account.");
    return;
  }

  const result = await apiGet("/api/employees/" + employeeId);
  if (result.status === 401) {
    handleApiResult(result);
    return;
  }
  if (result.status === 403 || result.status === 404) {
    showMessage("error", "This employee profile is unavailable for your account.");
    return;
  }
  if (!handleApiResult(result)) {
    return;
  }
  profileEmployee = result.data.employee;
  renderEmployeeHeader(profileEmployee);
  renderEmployeeBasics(profileEmployee);
  renderTabs();

  await Promise.all([
    loadHierarchy(profileEmployee),
    loadEmployeeSkills(employeeId),
    loadEmployeeSalary(employeeId),
    loadEmployeeProjects(employeeId),
    loadEmployeeJmlAndActivity(employeeId),
  ]);
  renderTabs();
})();
