// Dashboard: employee counts scoped to the signed-in user.

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "dashboard");
  showFlash();

  const viewLink = document.getElementById("view-link");
  const hierarchyLink = document.getElementById("hierarchy-link");
  const skillsLink = document.getElementById("skills-link");
  const salaryLink = document.getElementById("salary-link");
  const projectsLink = document.getElementById("projects-link");
  const jmlLink = document.getElementById("jml-link");
  const addLink = document.getElementById("add-link");

  if (!canReadProjects(user)) {
    projectsLink.hidden = true;
  }

  if (!canReadSkills(user)) {
    skillsLink.hidden = true;
  }

  if (!canReadSalary(user)) {
    salaryLink.hidden = true;
  }

  if (!canRead(user)) {
    const otherAccess = [];
    if (canReadProjects(user)) {
      otherAccess.push("projects");
    }
    if (canReadSkills(user)) {
      otherAccess.push("skills");
    }
    if (canReadSalary(user)) {
      otherAccess.push("salary");
    }

    document.getElementById("access-level").textContent = otherAccess.length
      ? "No employee access; " + otherAccess.join(", ")
      : "No employee access";
    viewLink.hidden = true;
    hierarchyLink.hidden = true;
    skillsLink.hidden = true;
    jmlLink.hidden = true;
    addLink.hidden = true;
    if (otherAccess.length === 0) {
      showMessage(
        "error",
        "Your role does not grant access to employee records, projects, skills, or salary."
      );
    }
    return;
  }

  document.getElementById("access-level").textContent = can(user, "readAll")
    ? "All employees"
    : "Assigned scope";

  if (!canCreate(user)) {
    addLink.hidden = true;
  }
  if (!canReadJml(user)) {
    jmlLink.hidden = true;
  }

  const result = await apiGet("/api/employees");
  if (!handleApiResult(result)) {
    return;
  }

  const employees = result.data.employees || [];
  document.getElementById("total-employees").textContent = String(employees.length);
  document.getElementById("active-employees").textContent = String(
    employees.filter(function (employee) {
      return employee.employment_status === "Active";
    }).length
  );
})();
