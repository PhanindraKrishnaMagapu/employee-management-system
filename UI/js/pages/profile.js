let currentProfile = null;

function profileValue(value) {
  return value === null || value === undefined || String(value).trim() === ""
    ? "Not available"
    : String(value);
}

function profileDate(value) {
  if (!value) {
    return "Not available";
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value));
  return match ? match[3] + "/" + match[2] + "/" + match[1] : String(value);
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

function formatProfileSalary(salary) {
  if (!salary) {
    return "No current salary record";
  }
  const amount = Number(salary.annual_salary);
  const currency = salary.currency || "";
  if (!Number.isFinite(amount)) {
    return "Not available";
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch (error) {
    return amount.toLocaleString() + (currency ? " " + currency : "");
  }
}

function setProfileText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = profileValue(value);
  }
}

function renderProfile(profile) {
  const user = profile.user || {};
  const employee = profile.employee || {};
  const fullName = [employee.first_name, employee.last_name]
    .filter(function (part) { return Boolean(part); })
    .join(" ");
  const displayName = fullName || user.username || "My Profile";
  const avatar = document.getElementById("profile-avatar");
  avatar.textContent = displayName.trim().charAt(0).toUpperCase() || "U";
  const photoPath = safeProfilePhoto(employee.profile_photo_path);
  if (photoPath) {
    const image = document.createElement("img");
    image.src = photoPath;
    image.alt = "";
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", function () { image.remove(); });
    avatar.appendChild(image);
  }

  setProfileText("profile-name", displayName);
  const employeeCode = employee.employee_code;
  document.getElementById("profile-hero-meta").textContent = employeeCode
    ? "Employee ID " + employeeCode
    : "No employee record is linked to this account";
  setProfileText("profile-full-name", fullName);
  setProfileText("profile-employee-id", employeeCode);
  setProfileText("profile-email", employee.official_email || user.email);
  setProfileText("profile-phone", employee.phone);
  setProfileText("profile-date-of-birth", profileDate(employee.date_of_birth));
  setProfileText("profile-location", employee.location);

  setProfileText("profile-designation", employee.designation);
  setProfileText("profile-department", employee.department);
  setProfileText("profile-manager", employee.manager_name);
  setProfileText("profile-joining-date", profileDate(employee.joining_date));
  setProfileText("profile-employment-type", employee.employment_type);
  setProfileText("profile-employment-status", employee.employment_status);
  setProfileText("profile-work-location", employee.location);

  const compensation = document.getElementById("compensation-section");
  compensation.hidden = !Object.prototype.hasOwnProperty.call(profile, "salary");
  if (!compensation.hidden) {
    setProfileText("profile-salary", formatProfileSalary(profile.salary));
    setProfileText(
      "profile-salary-effective-date",
      profileDate(profile.salary && profile.salary.effective_from)
    );
  }

  setProfileText("profile-username", user.username);
  setProfileText("profile-roles", (user.roles || []).join(" · "));
  setProfileText("profile-account-status", user.account_status);

  const canEditPhone = Array.isArray(profile.editable_fields) &&
    profile.editable_fields.includes("phone") && Boolean(profile.employee);
  document.getElementById("edit-profile-button").hidden = !canEditPhone;
  document.getElementById("profile-phone-input").value = employee.phone || "";
}

function openProfileEditor() {
  const form = document.getElementById("profile-edit-form");
  form.hidden = false;
  document.getElementById("edit-profile-button").hidden = true;
  document.getElementById("profile-phone-input").focus();
}

function closeProfileEditor() {
  document.getElementById("profile-edit-form").hidden = true;
  document.getElementById("edit-profile-button").hidden = false;
  document.getElementById("profile-phone-input").value =
    (currentProfile.employee && currentProfile.employee.phone) || "";
}

async function saveProfile(event) {
  event.preventDefault();
  const button = document.getElementById("profile-save-button");
  button.disabled = true;
  const phone = document.getElementById("profile-phone-input").value.trim();
  const result = await apiPut("/api/profile", { phone: phone || null });
  button.disabled = false;
  if (!handleApiResult(result)) {
    return;
  }
  currentProfile = result.data;
  renderProfile(currentProfile);
  document.getElementById("profile-edit-form").hidden = true;
  showMessage("success", "Profile updated.");
}

(async function initProfilePage() {
  const user = await requireAuth();
  if (!user) {
    return;
  }
  initShell(user, "profile");

  const result = await apiGet("/api/profile");
  if (!handleApiResult(result)) {
    return;
  }
  currentProfile = result.data;
  renderProfile(currentProfile);

  document.getElementById("edit-profile-button").addEventListener("click", openProfileEditor);
  document.getElementById("profile-cancel-button").addEventListener("click", closeProfileEditor);
  document.getElementById("profile-edit-form").addEventListener("submit", saveProfile);
})();
