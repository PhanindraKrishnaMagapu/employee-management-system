// Shared page shell, messages, and rendering helpers.

const FLASH_KEY = "ems_flash";

const NAV_ICONS = {
  dashboard:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"></rect><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"></rect><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"></rect><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"></rect></svg>',
  employees:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.25"></circle><path d="M3.5 19c.45-3.25 2.45-5 5.5-5s5.05 1.75 5.5 5M16 5.25a3.25 3.25 0 0 1 0 6.5M17 14.25c2.1.55 3.35 2.15 3.65 4.75"></path></svg>',
  hierarchy:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="3" width="8" height="5" rx="1.5"></rect><rect x="2.5" y="16" width="7" height="5" rx="1.5"></rect><rect x="14.5" y="16" width="7" height="5" rx="1.5"></rect><path d="M12 8v4m-6 4v-2h12v2m-6-4H6v2m6-2h6v2"></path></svg>',
  skills:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.7 5.45 6.02.88-4.36 4.25 1.03 6-5.39-2.83-5.39 2.83 1.03-6-4.36-4.25 6.02-.88L12 3Z"></path><path d="m9.5 12 1.6 1.6 3.5-3.6"></path></svg>',
  salaries:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 9h18M7 15h3m4-3.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z"></path></svg>',
  projects:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.5h6l2 2h8v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-11Z"></path><path d="M4 7.5v-2a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v2"></path></svg>',
  jml:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3.5h7l4 4V20a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 20V5a1.5 1.5 0 0 1 1-1.5Z"></path><path d="M14 3.5V8h4m-9 4h6m-6 4h6"></path></svg>',
  add:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.25"></circle><path d="M3.5 19c.45-3.25 2.45-5 5.5-5 2.05 0 3.65.8 4.65 2.3M18 10v7m-3.5-3.5h7"></path></svg>',
  leave:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"></rect><path d="M7.5 3.5v3M16.5 3.5v3M3.5 9.5h17M8 13h3m2 0h3m-8 3h3"></path></svg>',
  attendance:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3.5 2"></path></svg>',
  notifications:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"></path></svg>',
  reports:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V11m5 9V5m5 15v-7m5 7V8"></path></svg>',
  settings:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.6-1.4-2.4 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.6a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.6 1.4 2.4-1.4 1.1a7 7 0 0 1 0 2Z" transform="translate(-1 -1)"></path></svg>',
  help:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M9.5 9a2.6 2.6 0 1 1 4.4 1.9c-1.2 1-1.9 1.4-1.9 3.1M12 17.5v.1"></path></svg>',
};

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
    { key: "salaries", label: "Salary", href: "/pages/salaries.html", show: canReadSalary(user) },
    { key: "projects", label: "Projects", href: "/pages/projects.html", show: canReadProjects(user) },
    { key: "jml", label: "JML", href: "/pages/jml.html", show: canReadJml(user) },
    { key: "add", label: "Add Employee", href: "/pages/employee-form.html", show: canCreate(user) },
  ].filter(function (item) {
    return item.show;
  });
  const plannedItems = [
    { key: "leave", label: "Leave Management" },
    { key: "attendance", label: "Attendance" },
    { key: "notifications", label: "Notifications" },
    { key: "reports", label: "Reports & Analytics" },
    { key: "settings", label: "Settings" },
    { key: "help", label: "Help & Support" },
  ];

  const nav = document.getElementById("sidebar-nav");
  if (nav) {
    nav.setAttribute("aria-label", "Application navigation");
    const mainLinks = links
      .map(function (item) {
        const isActive = item.key === active;
        const activeClass = isActive ? "nav-link active" : "nav-link";
        const currentPage = isActive ? ' aria-current="page"' : "";
        return (
          '<a class="' + activeClass + '"' + currentPage + ' href="' + item.href + '">' +
          (NAV_ICONS[item.key] || "") +
          "<span>" + escapeHtml(item.label) + "</span></a>"
        );
      })
      .join("");
    const otherLinks = plannedItems
      .map(function (item) {
        return (
          '<span class="nav-link nav-link-planned" aria-disabled="true">' +
          (NAV_ICONS[item.key] || "") +
          '<span class="nav-link-label">' + escapeHtml(item.label) + "</span>" +
          '<span class="nav-status">Planned</span></span>'
        );
      })
      .join("");
    nav.innerHTML =
      '<div class="nav-section-label">MAIN MENU</div>' +
      mainLinks +
      '<div class="nav-section-label nav-section-other">OTHER</div>' +
      otherLinks;
  }

  const username = document.getElementById("username");
  if (username) {
    username.textContent = user.username || "";
  }

  const roles = document.getElementById("roles");
  if (roles) {
    roles.textContent = (user.roles || []).join(" · ") || "No roles";
  }

  setupShellHeader(user, username, roles);
  setupMobileNavigation();

  const logoutButton = document.getElementById("logout-button");
  if (logoutButton && !logoutButton.dataset.shellBound) {
    logoutButton.dataset.shellBound = "true";
    logoutButton.addEventListener("click", async function () {
      await logout();
      window.location.replace("/");
    });
  }
}

function setupShellHeader(user, username, roles) {
  const topbar = document.querySelector(".topbar");
  const content = document.querySelector(".content");
  if (!topbar || !content) {
    return;
  }

  let heading = topbar.querySelector(".topbar-heading");
  if (!heading) {
    heading = document.createElement("div");
    heading.className = "topbar-heading";
    const pageTitle = content.querySelector("h1");
    if (pageTitle) {
      pageTitle.classList.add("page-title");
      heading.appendChild(pageTitle);
    }
    topbar.insertBefore(heading, topbar.firstChild);
  }

  if (username && roles && !username.closest(".topbar-user")) {
    const userArea = document.createElement("div");
    userArea.className = "topbar-user";

    const profileLink = document.createElement("a");
    profileLink.className = "profile-link";
    profileLink.href = "/pages/profile.html";
    profileLink.setAttribute("aria-label", "Open My Profile");

    const initials = document.createElement("span");
    initials.className = "user-avatar";
    initials.setAttribute("aria-hidden", "true");
    initials.textContent = String(user.username || "U").trim().charAt(0).toUpperCase();

    const identity = document.createElement("div");
    identity.className = "user-identity";
    username.classList.add("user-name");
    roles.classList.add("user-role");
    identity.append(username, roles);
    profileLink.append(initials, identity);
    userArea.appendChild(profileLink);

    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {
      logoutButton.classList.add("header-logout");
      userArea.appendChild(logoutButton);
    }
    topbar.appendChild(userArea);
  }
}

function setupMobileNavigation() {
  const layout = document.querySelector(".layout");
  const sidebar = layout && layout.querySelector(".sidebar");
  const topbar = layout && layout.querySelector(".topbar");
  const nav = layout && layout.querySelector("#sidebar-nav");
  if (!layout || !sidebar || !topbar || !nav || sidebar.dataset.navigationReady) {
    return;
  }
  sidebar.dataset.navigationReady = "true";
  sidebar.id = "app-sidebar";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "nav-toggle";
  toggle.setAttribute("aria-controls", "app-sidebar");
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Open navigation");
  toggle.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"></path></svg>';
  topbar.insertBefore(toggle, topbar.firstChild);

  const backdrop = document.createElement("button");
  backdrop.type = "button";
  backdrop.className = "sidebar-backdrop";
  backdrop.setAttribute("aria-label", "Close navigation");
  backdrop.hidden = true;
  layout.insertBefore(backdrop, sidebar.nextSibling);

  function setNavigationOpen(isOpen, restoreFocus) {
    const mobileViewport = window.matchMedia
      ? window.matchMedia("(max-width: 48rem)").matches
      : window.innerWidth <= 768;
    sidebar.classList.toggle("is-open", isOpen);
    document.body.classList.toggle("navigation-open", isOpen);
    backdrop.hidden = !isOpen;
    sidebar.inert = mobileViewport && !isOpen;
    sidebar.setAttribute("aria-hidden", String(mobileViewport && !isOpen));
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    if (isOpen) {
      const firstLink = nav.querySelector("a");
      if (firstLink) {
        firstLink.focus();
      }
    } else if (restoreFocus) {
      toggle.focus();
    }
  }

  toggle.addEventListener("click", function () {
    setNavigationOpen(toggle.getAttribute("aria-expanded") !== "true", false);
  });
  backdrop.addEventListener("click", function () {
    setNavigationOpen(false, true);
  });
  nav.addEventListener("click", function (event) {
    if (event.target.closest("a")) {
      setNavigationOpen(false, false);
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
      setNavigationOpen(false, true);
    }
  });
  window.addEventListener("resize", function () {
    const mobileViewport = window.matchMedia
      ? window.matchMedia("(max-width: 48rem)").matches
      : window.innerWidth <= 768;
    if (!mobileViewport && toggle.getAttribute("aria-expanded") === "true") {
      setNavigationOpen(false, false);
    } else if (!mobileViewport) {
      sidebar.inert = false;
      sidebar.setAttribute("aria-hidden", "false");
    } else {
      const isOpen = toggle.getAttribute("aria-expanded") === "true";
      sidebar.inert = !isOpen;
      sidebar.setAttribute("aria-hidden", String(!isOpen));
    }
  });
  setNavigationOpen(false, false);
}
