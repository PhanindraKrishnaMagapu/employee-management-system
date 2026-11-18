// Login page behaviour.

(async function init() {
  if (getStoredUser()) {
    const user = await currentUser();
    if (user) {
      window.location.replace("/pages/dashboard.html");
      return;
    }
  }

  showFlash();

  const form = document.getElementById("login-form");
  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    showMessage("error", "");

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    if (!username || !password) {
      showMessage("error", "Enter both username and password.");
      return;
    }

    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    const result = await login(username, password);
    button.disabled = false;

    if (!result.ok) {
      showMessage("error", result.message);
      return;
    }

    setFlash("success", "Signed in successfully.");
    window.location.replace("/pages/dashboard.html");
  });
})();
