// Shared page shell, messages, and rendering helpers.

const FLASH_KEY = "ems_flash";

function escapeHtml(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setFlash(type, message) {
  sessionStorage.setItem(FLASH_KEY, JSON.stringify({ type, message }));
}

function takeFlash() {
  try {
    const raw = sessionStorage.getItem(FLASH_KEY);
    if (!raw) {
      return null;
    }
    sessionStorage.removeItem(FLASH_KEY);
    return JSON.parse(raw);
  } catch (error) {
    return null;
  }
}

function showMessage(type, message) {
  const box = document.getElementById("message");
  if (!box) {
    return;
  }
  box.className = "message " + (type === "success" ? "success" : "error");
  box.textContent = message || "";
  box.hidden = !message;
}

function showFlash() {
  const flash = takeFlash();
  if (flash) {
    showMessage(flash.type, flash.message);
  }
}

// Returns true only when the call succeeded. Redirects on an expired session.
function handleApiResult(result) {
  if (result.status === 401) {
    clearUser();
    window.location.replace("/");
    return false;
  }
  if (!result.ok) {
    showMessage("error", result.data.message || "The request could not be completed.");
    return false;
  }
  return true;
}

function initShell(user, active) {
  const links = [
    { key: "dashboard", label: "Dashboard", href: "/pages/dashboard.html", show: true },
    { key: "employees", label: "Employees", href: "/pages/employees.html", show: canRead(user) },
    { key: "hierarchy", label: "Hierarchy", href: "/pages/hierarchy.html", show: canRead(user) },
    { key: "skills", label: "Skills", href: "/pages/skills.html", show: canReadSkills(user) },
    { key: "salaries", label: "Salaries", href: "/pages/salaries.html", show: canReadSalary(user) },
    { key: "projects", label: "Projects", href: "/pages/projects.html", show: canReadProjects(user) },
    { key: "jml", label: "JML", href: "/pages/jml.html", show: canReadJml(user) },
    { key: "add", label: "Add Employee", href: "/pages/employee-form.html", show: canCreate(user) },
  ].filter(function (item) {
    return item.show;
  });

  const nav = document.getElementById("sidebar-nav");
  if (nav) {
    nav.innerHTML = links
      .map(function (item) {
        const activeClass = item.key === active ? ' class="active"' : "";
        return '<a href="' + item.href + '"' + activeClass + ">" + escapeHtml(item.label) + "</a>";
      })
      .join("");
  }

  const username = document.getElementById("username");
  if (username) {
    username.textContent = user.username || "";
  }

  const roles = document.getElementById("roles");
  if (roles) {
    roles.textContent = (user.roles || []).join(", ") || "No roles";
  }

  const logoutButton = document.getElementById("logout-button");
  if (logoutButton) {
    logoutButton.addEventListener("click", async function () {
      await logout();
      window.location.replace("/");
    });
  }
}
