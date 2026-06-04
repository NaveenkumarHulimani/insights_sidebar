# Insights Sidebar

A Frappe custom app that **dynamically injects Insights dashboards into the Desk
sidebar based on user roles** and renders them **in-place inside the Desk via an
iframe** — no new browser tab, no full page reload, and no workspace switch. The
clicked sidebar item stays highlighted while its dashboard loads in a native-looking
frame.

Built and tested on **Frappe v16** (the same approach works on v14 / v15).

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [How to configure a new link](#how-to-configure-a-new-link)
- [How to verify role-based visibility](#how-to-verify-role-based-visibility)
- [Security model](#security-model)
- [Performance / caching](#performance--caching)
- [Deletion cleanup (live UI removal)](#deletion-cleanup-live-ui-removal)
- [Configuration keys (no hardcoding)](#configuration-keys-no-hardcoding)
- [Installation](#installation)
- [File map](#file-map)

---

## What it does

| Requirement | Implementation |
|---|---|
| Configuration DocType | **Insights Sidebar Config** — `Label` (Data), `Dashboard` (Link → *Insights Dashboard*), `Roles` (Table → *Has Role*). |
| Role-based visibility | Server filters links by `frappe.get_roles()` **and** `frappe.has_permission` on the dashboard. |
| Dynamic sidebar update | Client bundle injected via `app_include_js` re-renders on `frappe.router` change and `MutationObserver`. |
| In-place viewer | Custom Desk **Page** `insights-viewer` hosting an `<iframe>`; navigation via `frappe.set_route` (SPA, no reload). |
| Active highlight | Item carries Frappe's native `active-sidebar` class for the current route. |
| Delete cleanup | `on_trash` controller clears the cache **and** pushes a realtime event to remove the item from open UIs. |
| Caching | Full link set cached in Redis; rebuilt only when a config changes. |
| No hardcoding | Dashboard doctype, base path and URL pattern are all resolved / overridable via `site_config`. |

---

## Architecture

```
                      Desk (browser)
 ┌───────────────────────────────────────────────────────────┐
 │  app_include_js: public/js/insights_sidebar.js            │
 │   • get_sidebar_links()  ──► injects items into            │
 │     .body-sidebar .sidebar-items  (native markup)          │
 │   • re-injects on router change / MutationObserver         │
 │   • click → frappe.set_route('insights-viewer', <dash>)    │
 │                                                            │
 │  Page: insights-viewer  (page/insights_viewer/*)           │
 │   • get_dashboard_view(dash)  ──► <iframe src=/insights/…> │
 └───────────────▲───────────────────────────────────────────┘
                 │ whitelisted, permission-checked
 ┌───────────────┴───────────────────────────────────────────┐
 │  api.py                                                    │
 │   • get_sidebar_links()    role + has_permission filter    │
 │   • get_dashboard_view()   server-side permission gate     │
 │   • cached link set (Redis), cleared by the controller     │
 │                                                            │
 │  Insights Sidebar Config (controller)                      │
 │   • validate / after_insert / on_update / on_trash         │
 │   • clear_cache() + frappe.publish_realtime()              │
 └────────────────────────────────────────────────────────────┘
```

The sidebar item is a normal anchor (`href="/app/insights-viewer/<dashboard>"`),
so Frappe's own `is_route_in_sidebar()` matches the current route and applies the
`active-sidebar` class — we additionally set it ourselves for robustness, since v16
rebuilds the sidebar on every route change.

---

## Two injection modes (hooks **or** Workspace documents)

The app ships **both** approaches the assignment mentions — pick per site:

### 1. JS injection (default)
`app_include_js` injects the role-filtered items into the live Desk sidebar
(`.body-sidebar .sidebar-items`), re-injecting on route change. Gives a grouped
**"Insights"** section and precise, per-request role + `has_permission` filtering.

### 2. Workspace-document mode (`get_side_bar_items` / Workspace API)
Each enabled config maintains a native **Workspace** document (`type = URL`)
that links to the in-place viewer. Visibility is enforced **natively** by Frappe
via the Workspace `roles` table (mirrored from the config) — so role filtering is
done by core `get_workspace_sidebar_items()` and cached in the bootinfo, with
**zero** custom queries per page load. A small capture-phase click-shim keeps the
`URL` link routing in-place (no reload, no new tab).

Enable it:

```bash
bench --site <site> set-config insights_sidebar_use_workspace 1
# optional: if your Desk is not at /app (e.g. /desk)
bench --site <site> set-config insights_sidebar_desk_path /desk
bench --site <site> execute insights_sidebar.workspace_sync.rebuild_workspaces
bench --site <site> clear-cache
```

The bundle reads the active mode from the bootinfo (`extend_bootinfo`) and skips
DOM injection when workspace mode is on, so the two never double up. Switch back
with `set-config insights_sidebar_use_workspace 0` then
`execute insights_sidebar.workspace_sync.clear_managed_workspaces`.

> **Design note:** the managed Workspace deliberately sets **no `module`** — a
> module-bound Workspace is hidden from users who can't access that module
> (`Workspace.__init__` raises `PermissionError`), which would override the role
> gate. With no module, only the `roles` table governs visibility. Implemented in
> [workspace_sync.py](insights_sidebar/workspace_sync.py).

## How to configure a new link

1. Make sure the **Insights** app is installed on the site and at least one
   **Insights Dashboard** exists.
2. Go to **Insights Sidebar Config → New** (or search "Insights Sidebar Config" in
   the awesomebar).
3. Fill in:
   - **Label** — the text shown in the sidebar (e.g. *Sales Overview*).
   - **Dashboard** — pick the Insights Dashboard to embed.
   - **Visible To Roles** — add one or more roles (e.g. *Sales Manager*). The item
     is shown only to users who have **at least one** of these roles. At least one
     role is required.
   - **Enabled** — leave checked (uncheck to hide without deleting).
4. **Save.** The new item appears in the Desk sidebar for permitted users
   immediately (open sessions update live; no refresh needed).

> Tip: from a saved config you can click **Open in Viewer** to preview the embedded
> dashboard.

---

## How to verify role-based visibility

1. Create a config whose **Roles** table contains, say, only *Sales Manager*.
2. **As an Administrator / System Manager** without that role, open the Desk — the
   item should **not** appear (System Manager is not in the configured roles).
3. Add the *Sales Manager* role to a test user (User → Roles), log in as that user
   in another browser/incognito window — the item **appears**.
4. Remove the role and reload — the item **disappears**.
5. Quick server-side check from `bench console`:

   ```python
   import frappe
   from insights_sidebar.api import get_sidebar_links
   frappe.set_user("test_user@example.com")
   frappe.get_roles()              # confirm roles
   get_sidebar_links()             # only links the user may see
   frappe.set_user("Administrator")
   ```

Visibility is enforced **server-side** — the client never receives links the user
is not entitled to, so it cannot be bypassed from the browser.

---

## Security model

- **Role filter:** `get_sidebar_links()` intersects the config's roles with
  `frappe.get_roles()` of the current user.
- **Permission gate:** every link is additionally checked with
  `frappe.has_permission("Insights Dashboard", "read", doc=<dashboard>)` — a user
  who has a matching role but no read permission on the dashboard still does not see
  it.
- **Iframe access control:** the viewer never trusts the route. `get_dashboard_view()`
  re-validates `has_permission` server-side and only then returns the embed URL, so
  manually crafting `/app/insights-viewer/<dashboard>` cannot load a dashboard the
  user may not read (it returns a `PermissionError`).
- The iframe is **same-origin and session-authenticated** (`/insights/...`), so the
  Insights app enforces its own permissions too (defence in depth).

---

## Performance / caching

- The full set of enabled configs (with their roles) is read **once** and cached in
  Redis under `insights_sidebar_links` (`frappe.cache()`).
- Page loads call `get_sidebar_links()`, which reads the **cache** and applies a
  cheap in-memory role/permission filter — **no per-refresh table scans**.
- The cache is invalidated **only** when a config is created, updated or deleted
  (controller → `clear_cache()`).

---

## Deletion cleanup (live UI removal)

The assignment requires that deleting a config removes the item from the UI. The
**`on_trash`** controller:

1. `clear_cache()` so the link never returns from the server again, and
2. `frappe.publish_realtime("insights_sidebar_item_removed", …)` (site-wide) so every
   open Desk session removes the item from the sidebar **immediately, without a
   refresh**. If a user is currently viewing the deleted dashboard, they get a
   notice.

`after_insert` / `on_update` similarly emit `insights_sidebar_changed` so additions
and edits appear live.

---

## Configuration keys (no hardcoding)

No dashboard id or role name is hardcoded. The following are resolved from data or
overridable in `site_config.json` for non-default deployments / Insights versions:

| Key | Default | Purpose |
|---|---|---|
| `insights_dashboard_doctype` | `Insights Dashboard` | Link target doctype. |
| `insights_dashboard_base_path` | `/insights` | Base path of the Insights SPA. |
| `insights_dashboard_url_pattern` | auto (`/dashboards/{name}` for v3, `/dashboard/{name}` for v2) | Per-dashboard URL pattern. |

Example:

```bash
bench --site <site> set-config insights_dashboard_base_path /insights
```

### Insights v2 vs v3

Insights **v3** (workbook-based) stores dashboards in the **`Insights Dashboard v3`**
doctype and renders a single dashboard at **`/insights/dashboards/<name>`** (plural),
while **v2** uses **`Insights Dashboard`** at **`/insights/dashboard/<name>`**
(singular). The app picks the correct URL automatically from the configured doctype
(override with `insights_dashboard_url_pattern` if needed). Point the app at the
right doctype for your install:

```bash
# Insights v3 (workbook dashboards)
bench --site <site> set-config insights_dashboard_doctype "Insights Dashboard v3"
# then set the Dashboard field's "Options" to "Insights Dashboard v3" too
```

The shipped DocType is set to `Insights Dashboard v3` (the current Insights). For
v2, change both the field `options` and `insights_dashboard_doctype` back to
`Insights Dashboard`.

> **v3 permissions:** v3 dashboards use Insights' team/resource permission model, so
> a user needs *both* a configured role **and** Insights access (owner / admin /
> team share) to see the link — exactly what the `has_permission` gate enforces.

### Quick demo data (populated dashboard)

To get a real, chart-filled dashboard to link to, use Insights' bundled demo set:

```python
# bench --site <site> console
import os; os.environ["CI"] = "1"          # use the bundled duckdb, skip download
from insights.setup.demo import DemoDataFactory
DemoDataFactory.run(force=True)             # creates "Order Analysis" workbook + dashboard
frappe.db.commit()
```

Then create a config whose **Dashboard** is the new `Insights Dashboard v3` record.

---

## Installation

```bash
# from the bench directory
bench get-app insights            # prerequisite: provides "Insights Dashboard"
bench get-app https://github.com/<you>/insights_sidebar   # or copy into apps/
bench --site <site> install-app insights_sidebar
bench --site <site> migrate
bench build --app insights_sidebar
bench --site <site> clear-cache
```

Reload the Desk. Configure a link as above.

---

## File map

```
insights_sidebar/
├── pyproject.toml
├── README.md
├── license.txt
└── insights_sidebar/
    ├── hooks.py                      # app_include_js/css
    ├── api.py                        # cached, role/permission-filtered endpoints
    ├── modules.txt                   # "Insights Sidebar"
    ├── public/
    │   ├── js/insights_sidebar.js    # sidebar injector (the core)
    │   └── css/insights_sidebar.css  # native styling + iframe viewer
    └── insights_sidebar/
        ├── doctype/insights_sidebar_config/
        │   ├── insights_sidebar_config.json   # the configuration DocType
        │   ├── insights_sidebar_config.py     # validate / on_trash cleanup
        │   └── insights_sidebar_config.js
        └── page/insights_viewer/
            ├── insights_viewer.json           # custom Desk Page
            └── insights_viewer.js              # in-place iframe viewer
```
