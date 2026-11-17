# API documentation

Status: no REST endpoints yet. Phase 3 will add the first routes.

## Contract agreed in Phase 1

- Base URL on your machine: `http://127.0.0.1:5000`
- The frontend reads that address from `UI/js/api.js` (`API_BASE_URL`).
- The API will return JSON.
- HTML stays in `UI/`. Flask will not render the product pages.
- Routes will be Flask blueprints under `BACKEND/app/routes/`, registered from `BACKEND/app/__init__.py`.
- Phase 1 registers no blueprints, so the running app has an empty URL map.

## Planned response shape

Later phases will use one JSON shape so every screen can handle success and failure the same way.

Success:

```json
{ "data": {}, "error": null }
```

Failure:

```json
{ "data": null, "error": { "code": "not_found", "message": "Employee not found" } }
```

Nothing in the repository returns this JSON yet.

## Planned areas

Employee, authentication, organization, JML, projects, skills, salary, dashboard, reports, and audit. Each area is documented here when its routes are added. Login and role checks are Phase 6. Until then, do not put real employee data behind this API.

See [architecture.md](architecture.md).
