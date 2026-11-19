// Session handling and role-based UI gating.
// The server remains authoritative: every API response is still checked by
// the page, and 401/403 responses are handled explicitly.

const SESSION_KEY = "ems_user";

const CREATE_FORM_FIELDS = [
  "employee_code",
  "first_name",
  "last_name",
  "official_email",
  "phone",
  "joining_date",
  "employment_type",
  "employment_status",
  "location",
  "department_id",
  "designation_id",
  "manager_id",
  "profile_photo_path",
];

const LIMITED_UPDATE_FIELDS = ["phone", "location"];
const SELF_UPDATE_FIELDS = ["phone"];

// Mirrors BACKEND/app/auth/permissions.py so controls can be hidden early.
// It is not a security boundary; the backend enforces the real permissions.
const ROLE_CAPABILITIES = {
  CEO: ["readAll", "jmlRead", "projectRead", "skillsRead"],
  "HR Admin": [
    "readAll",
    "create",
    "updateFull",
    "archive",
    "salaryManage",
    "jmlManage",
    "projectRead",
    "projectManage",
    "employeePicker",
    "skillsManage",
  ],
  "HR Executive": ["readScoped", "updateLimited", "jmlRead", "skillsRead"],
  "Department Manager": [
    "readScoped",
    "updateLimited",
    "jmlRead",
    "projectRead",
    "skillsRead",
  ],
  "Project Manager": ["projectRead", "projectManage", "employeePicker"],
  Employee: ["readScoped", "updateSelf", "skillsRead"],
  "Payroll Admin": ["salaryRead"],
};

function getStoredUser() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

function storeUser(user) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
}

function clearUser() {
  sessionStorage.removeItem(SESSION_KEY);
}

function can(user, capability) {
  if (!user || !Array.isArray(user.roles)) {
    return false;
  }
  return user.roles.some(function (role) {
    return (ROLE_CAPABILITIES[role] || []).indexOf(capability) !== -1;
  });
}

function canRead(user) {
  return can(user, "readAll") || can(user, "readScoped");
}

function canCreate(user) {
  return can(user, "create");
}

function canArchive(user) {
  return can(user, "archive");
}

// HR Admin has jml:manage but not jml:read, so manage implies read access.
function canReadJml(user) {
  return can(user, "jmlRead") || can(user, "jmlManage");
}

function canManageJml(user) {
  return can(user, "jmlManage");
}

// Project access is separate from general employee access. Project Managers
// intentionally do not receive readAll/readScoped/jmlRead capabilities here.
function canReadProjects(user) {
  return can(user, "projectRead") || can(user, "projectManage");
}

function canManageProjects(user) {
  return can(user, "projectManage");
}

function canSelectProjectEmployees(user) {
  return can(user, "employeePicker");
}

// HR Admin has skills:manage but not skills:read, so manage implies read access.
function canReadSkills(user) {
  return can(user, "skillsRead") || can(user, "skillsManage");
}

function canManageSkills(user) {
  return can(user, "skillsManage");
}

// Salary access is separate from employee access. HR Admin manages records;
// Payroll Admin retains read-only access. Manage also permits reading.
function canReadSalary(user) {
  return can(user, "salaryRead") || can(user, "salaryManage");
}

function canManageSalary(user) {
  return can(user, "salaryManage");
}

function canEdit(user) {
  return can(user, "updateFull") || can(user, "updateLimited") || can(user, "updateSelf");
}

function editableFieldsFor(user) {
  if (can(user, "updateFull")) {
    return CREATE_FORM_FIELDS.slice();
  }
  if (can(user, "updateLimited")) {
    return LIMITED_UPDATE_FIELDS.slice();
  }
  if (can(user, "updateSelf")) {
    return SELF_UPDATE_FIELDS.slice();
  }
  return [];
}

async function login(username, password) {
  const result = await apiPost("/api/auth/login", { username, password });
  if (result.ok && result.data.success && result.data.user) {
    storeUser(result.data.user);
    return { ok: true, user: result.data.user };
  }
  return { ok: false, message: result.data.message || "Login failed" };
}

async function logout() {
  await apiPost("/api/auth/logout", {});
  clearUser();
}

async function currentUser() {
  const result = await apiGet("/api/auth/me");
  if (result.ok && result.data.success && result.data.user) {
    storeUser(result.data.user);
    return result.data.user;
  }
  clearUser();
  return null;
}

async function requireAuth() {
  if (!getStoredUser()) {
    window.location.replace("/");
    return null;
  }
  const user = await currentUser();
  if (!user) {
    window.location.replace("/");
    return null;
  }
  return user;
}
