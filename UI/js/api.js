// Browser helpers for the Flask REST API.
// Pages are served by Flask from the same origin, so relative URLs work and
// the session cookie is sent with every request.

const API_BASE_URL = "";

async function apiRequest(path, options = {}) {
  const config = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: {},
  };

  if (options.body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, config);
  } catch (error) {
    return {
      ok: false,
      status: 0,
      data: { message: "Cannot reach the server. Check that the Flask app is running." },
    };
  }

  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const message = (data && data.message) || `Request failed (${response.status})`;
    return {
      ok: false,
      status: response.status,
      data: Object.assign({}, data || {}, { message }),
    };
  }

  return { ok: true, status: response.status, data: data || {} };
}

function apiGet(path) {
  return apiRequest(path);
}

function apiPost(path, body) {
  return apiRequest(path, { method: "POST", body });
}

function apiPut(path, body) {
  return apiRequest(path, { method: "PUT", body });
}

function apiDelete(path) {
  return apiRequest(path, { method: "DELETE" });
}
