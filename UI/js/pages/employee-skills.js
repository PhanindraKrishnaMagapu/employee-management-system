// Employee skill assignments: view, filter, assign, update, and remove.

let skillsPageUser = null;
let skillsEmployeeId = null;
let skillsEmployee = null;
let employeeAssignments = [];
let skillCatalog = [];

function skillValueOrDash(value) {
  return value === null || value === undefined || value === ""
    ? "-"
    : String(value);
}

function employeeName(employee) {
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

function renderEmployeeSummary(employee) {
  const rows = [
    ["Employee", employeeName(employee)],
    ["Employee code", employee.employee_code],
    ["Official email", employee.official_email],
    ["Status", employee.employment_status],
    ["Location", employee.location],
  ];

  document.getElementById("employee-summary").innerHTML = rows
    .map(function (row) {
      return (
        "<div>" +
        '<span class="label">' + escapeHtml(row[0]) + "</span>" +
        escapeHtml(skillValueOrDash(row[1])) +
        "</div>"
      );
    })
    .join("");
}

function proficiencyOptions(current) {
  const levels = ["Beginner", "Intermediate", "Advanced", "Expert"];
  return levels
    .map(function (level) {
      const selected = level === current ? " selected" : "";
      return '<option value="' + level + '"' + selected + ">" + level + "</option>";
    })
    .join("");
}

function matchesAssignmentFilters(assignment, term, level) {
  const skill = assignment.skill || {};
  if (level && assignment.proficiency_level !== level) {
    return false;
  }
  if (!term) {
    return true;
  }
  return [
    skill.name,
    skill.description,
    assignment.proficiency_level,
    assignment.last_verified,
  ]
    .join(" ")
    .toLowerCase()
    .indexOf(term) !== -1;
}

function renderAssignments() {
  const term = document.getElementById("skill-search").value.trim().toLowerCase();
  const level = document.getElementById("level-filter").value;
  const rows = employeeAssignments.filter(function (assignment) {
    return matchesAssignmentFilters(assignment, term, level);
  });

  document.getElementById("skill-rows").innerHTML = rows
    .map(function (assignment) {
      const skill = assignment.skill || {};
      const id = Number(assignment.id);
      const actions = canManageSkills(skillsPageUser)
        ? '<button type="button" class="link" data-save="' + id + '">Save</button> ' +
          '<button type="button" class="link danger" data-remove="' + id +
          '">Remove</button>'
        : "";
      const proficiency = canManageSkills(skillsPageUser)
        ? '<select class="assignment-control" data-field="proficiency">' +
          proficiencyOptions(assignment.proficiency_level) +
          "</select>"
        : '<span class="badge">' +
          escapeHtml(assignment.proficiency_level) +
          "</span>";
      const experience = canManageSkills(skillsPageUser)
        ? '<input class="assignment-control" data-field="experience" type="number" ' +
          'min="0" step="0.5" value="' +
          escapeHtml(Number(assignment.experience_years || 0)) + '">'
        : escapeHtml(Number(assignment.experience_years || 0));
      const verified = canManageSkills(skillsPageUser)
        ? '<input class="assignment-control" data-field="verified" type="date" value="' +
          escapeHtml(skillValueOrDash(assignment.last_verified)) + '">'
        : escapeHtml(skillValueOrDash(assignment.last_verified));

      return (
        "<tr>" +
        "<td>" + escapeHtml(skill.name || "Skill #" + assignment.skill_id) + "</td>" +
        "<td>" + escapeHtml(skillValueOrDash(skill.description)) + "</td>" +
        "<td>" + proficiency + "</td>" +
        "<td>" + experience + "</td>" +
        "<td>" + verified + "</td>" +
        '<td class="actions-cell">' + actions + "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("assignment-empty").hidden = rows.length !== 0;

  document.querySelectorAll("[data-save]").forEach(function (button) {
    button.addEventListener("click", async function () {
      await updateAssignment(Number(button.getAttribute("data-save")), button);
    });
  });

  document.querySelectorAll("[data-remove]").forEach(function (button) {
    button.addEventListener("click", async function () {
      await removeAssignment(Number(button.getAttribute("data-remove")));
    });
  });
}

async function loadEmployeeSkills() {
  const result = await apiGet("/api/employees/" + skillsEmployeeId + "/skills");
  if (!handleApiResult(result)) {
    return false;
  }

  skillsEmployee = result.data.employee;
  employeeAssignments = Array.isArray(result.data.assignments)
    ? result.data.assignments
    : [];
  renderEmployeeSummary(skillsEmployee);
  renderAssignments();
  renderAssignableSkills();
  return true;
}

async function loadSkillCatalog() {
  const result = await apiGet("/api/skills");
  if (!handleApiResult(result)) {
    return false;
  }
  skillCatalog = Array.isArray(result.data.skills) ? result.data.skills : [];
  return true;
}

function renderAssignableSkills() {
  if (!canManageSkills(skillsPageUser)) {
    return;
  }

  const assignedIds = new Set(
    employeeAssignments.map(function (item) {
      return Number(item.skill_id);
    })
  );
  const options = skillCatalog.filter(function (skill) {
    return !assignedIds.has(Number(skill.id));
  });

  const select = document.getElementById("skill");
  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = options.length
    ? "Select a skill"
    : "No additional skills available";
  select.appendChild(placeholder);

  options.forEach(function (skill) {
    const option = document.createElement("option");
    option.value = String(skill.id);
    option.textContent = skill.name;
    select.appendChild(option);
  });

  document.getElementById("assign-button").disabled = options.length === 0;
}

async function assignSkill(event) {
  event.preventDefault();
  showMessage("error", "");

  const skillId = Number(document.getElementById("skill").value);
  if (!skillId) {
    showMessage("error", "Select a skill to assign.");
    return;
  }

  const payload = {
    skill_id: skillId,
    proficiency_level: document.getElementById("proficiency").value,
    experience_years: Number(document.getElementById("experience").value || 0),
    last_verified: document.getElementById("last-verified").value || null,
  };
  if (!Number.isFinite(payload.experience_years) || payload.experience_years < 0) {
    showMessage("error", "Experience must be a non-negative number.");
    return;
  }

  const button = document.getElementById("assign-button");
  button.disabled = true;
  const result = await apiPost(
    "/api/employees/" + skillsEmployeeId + "/skills",
    payload
  );
  button.disabled = false;

  if (!handleApiResult(result)) {
    renderAssignableSkills();
    return;
  }

  showMessage("success", result.data.message || "Skill assigned.");
  document.getElementById("last-verified").value = "";
  document.getElementById("experience").value = "0";
  await loadEmployeeSkills();
}

async function updateAssignment(assignmentId, button) {
  showMessage("error", "");
  const row = button.closest("tr");
  const experience = Number(
    row.querySelector('[data-field="experience"]').value
  );
  if (!Number.isFinite(experience) || experience < 0) {
    showMessage("error", "Experience must be a non-negative number.");
    return;
  }

  const payload = {
    proficiency_level: row.querySelector('[data-field="proficiency"]').value,
    experience_years: experience,
    last_verified:
      row.querySelector('[data-field="verified"]').value || null,
  };

  button.disabled = true;
  const result = await apiPut(
    "/api/employees/" + skillsEmployeeId + "/skills/" + assignmentId,
    payload
  );
  button.disabled = false;

  if (!handleApiResult(result)) {
    return;
  }
  showMessage("success", result.data.message || "Employee skill updated.");
  await loadEmployeeSkills();
}

async function removeAssignment(assignmentId) {
  if (!window.confirm("Remove this skill from the employee?")) {
    return;
  }

  showMessage("error", "");
  const result = await apiDelete(
    "/api/employees/" + skillsEmployeeId + "/skills/" + assignmentId
  );
  if (!handleApiResult(result)) {
    return;
  }

  showMessage("success", result.data.message || "Employee skill removed.");
  await loadEmployeeSkills();
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  skillsPageUser = user;
  initShell(user, "skills");
  showFlash();

  if (!canReadSkills(user)) {
    showMessage("error", "Your role does not grant access to skills.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  skillsEmployeeId = Number(params.get("employee_id"));
  if (!Number.isInteger(skillsEmployeeId) || skillsEmployeeId <= 0) {
    showMessage("error", "No employee was selected.");
    return;
  }

  document.getElementById("skill-search").addEventListener("input", renderAssignments);
  document.getElementById("level-filter").addEventListener("change", renderAssignments);

  if (canManageSkills(user)) {
    document.getElementById("assignment-panel").hidden = false;
    document.getElementById("assignment-form").addEventListener("submit", assignSkill);
  }

  const catalogLoaded = await loadSkillCatalog();
  if (catalogLoaded) {
    await loadEmployeeSkills();
  }
})();
