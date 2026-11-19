// Skill catalog: search, add, and edit links.

let allSkills = [];
let skillsPageUser = null;

function skillValueOrDash(value) {
  return value === null || value === undefined || value === ""
    ? "-"
    : String(value);
}

function matchesSkillSearch(skill, term) {
  if (!term) {
    return true;
  }
  return [skill.name, skill.description]
    .join(" ")
    .toLowerCase()
    .indexOf(term) !== -1;
}

function renderSkillRows() {
  const term = document.getElementById("search").value.trim().toLowerCase();
  const rows = allSkills.filter(function (skill) {
    return matchesSkillSearch(skill, term);
  });

  document.getElementById("skill-rows").innerHTML = rows
    .map(function (skill) {
      const id = Number(skill.id);
      const edit = canManageSkills(skillsPageUser)
        ? '<a class="link" href="/pages/skill-form.html?id=' + id + '">Edit</a>'
        : "";

      return (
        "<tr>" +
        "<td>" + escapeHtml(skill.name) + "</td>" +
        "<td>" + escapeHtml(skillValueOrDash(skill.description)) + "</td>" +
        '<td class="actions-cell">' + edit + "</td>" +
        "</tr>"
      );
    })
    .join("");

  document.getElementById("empty").hidden = rows.length !== 0;
}

async function loadSkills() {
  const result = await apiGet("/api/skills");
  if (!handleApiResult(result)) {
    return;
  }
  allSkills = Array.isArray(result.data.skills) ? result.data.skills : [];
  renderSkillRows();
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

  if (!canManageSkills(user)) {
    document.getElementById("create-link").hidden = true;
  }

  document.getElementById("search").addEventListener("input", renderSkillRows);
  await loadSkills();
})();
