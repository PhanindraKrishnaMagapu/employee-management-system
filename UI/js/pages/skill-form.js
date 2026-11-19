// Create or edit a skill. Management is enforced by the API as well.

let skillFormId = null;

function setFormValue(id, value) {
  document.getElementById(id).value =
    value === null || value === undefined ? "" : String(value);
}

function collectSkillFormPayload() {
  return {
    name: document.getElementById("skill-name").value.trim(),
    description: document.getElementById("description").value.trim() || null,
  };
}

function disableSkillForm(message) {
  document.getElementById("submit-button").disabled = true;
  showMessage("error", message);
}

async function loadSkillForEdit() {
  const result = await apiGet("/api/skills");
  if (!handleApiResult(result)) {
    return false;
  }

  const skills = Array.isArray(result.data.skills) ? result.data.skills : [];
  const skill = skills.find(function (item) {
    return Number(item.id) === skillFormId;
  });
  if (!skill) {
    return false;
  }

  setFormValue("skill-name", skill.name);
  setFormValue("description", skill.description);
  return true;
}

async function submitSkillForm(event) {
  event.preventDefault();
  showMessage("error", "");

  const payload = collectSkillFormPayload();
  const button = document.getElementById("submit-button");
  button.disabled = true;

  const result = skillFormId === null
    ? await apiPost("/api/skills", payload)
    : await apiPut("/api/skills/" + skillFormId, payload);

  button.disabled = false;
  if (!handleApiResult(result)) {
    return;
  }

  setFlash("success", result.data.message || "Skill saved.");
  window.location.replace("/pages/skills.html");
}

(async function init() {
  const user = await requireAuth();
  if (!user) {
    return;
  }

  initShell(user, "skills");
  showFlash();

  if (!canManageSkills(user)) {
    disableSkillForm("Your role does not grant permission to manage skills.");
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const rawId = params.get("id");
  if (rawId !== null && rawId !== "") {
    skillFormId = Number(rawId);
    if (!Number.isInteger(skillFormId) || skillFormId <= 0) {
      disableSkillForm("No valid skill was selected.");
      return;
    }
    document.getElementById("page-title").textContent = "Edit Skill";
    document.getElementById("page-subtitle").textContent =
      "Update the selected skill's details.";
    document.getElementById("submit-button").textContent = "Save changes";
    const loaded = await loadSkillForEdit();
    if (!loaded) {
      disableSkillForm("The selected skill could not be loaded.");
      return;
    }
  }

  document.getElementById("skill-form").addEventListener("submit", submitSkillForm);
})();
