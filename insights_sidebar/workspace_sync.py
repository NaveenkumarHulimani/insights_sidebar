# Copyright (c) 2026, Naveenkumar Hulimani and contributors
# For license information, please see license.txt
"""Workspace-document-based sidebar injection (alternative to JS injection).

This is the "Workspace modifiers" path the assignment mentions alongside hooks.
Instead of injecting DOM nodes, it programmatically maintains one **Workspace**
document per ``Insights Sidebar Config``:

* the Workspace is a direct link (``type = "URL"``) to the in-place viewer route,
  so it appears natively in the Desk sidebar and routes without a reload;
* visibility is enforced **natively** by Frappe via the Workspace ``roles``
  table (mirrored from the config), giving per-item role-based visibility that
  Frappe itself caches in the bootinfo - no custom query per page load.

Enable it with::

    bench --site <site> set-config insights_sidebar_use_workspace 1
    bench --site <site> execute insights_sidebar.workspace_sync.rebuild_workspaces

When enabled, the client bundle detects the mode (via bootinfo) and skips DOM
injection so the two approaches never double up.
"""

import frappe

from insights_sidebar.api import VIEWER_ROUTE

# Managed workspaces are tagged with this app marker (NOT a module). We avoid
# setting `module` on purpose: Frappe hides a workspace whose module the user
# cannot access (raises PermissionError in Workspace.__init__), which would
# defeat pure role-based visibility. With no module, only the `roles` gate
# applies - exactly what we want.
MANAGED_APP = "insights_sidebar"


# ---------------------------------------------------------------------------
# Mode
# ---------------------------------------------------------------------------
def use_workspace_mode() -> bool:
	return bool(frappe.conf.get("insights_sidebar_use_workspace"))


def _viewer_url(dashboard: str) -> str:
	# The Desk path defaults to /app; overridable for sites that mount it
	# elsewhere (e.g. /desk). Normal clicks are routed in-place by the bundle's
	# click-shim regardless of this prefix.
	prefix = (frappe.conf.get("insights_sidebar_desk_path") or "/app").rstrip("/")
	return f"{prefix}/{VIEWER_ROUTE}/{frappe.utils.quote(dashboard)}"


# ---------------------------------------------------------------------------
# Sync a single config -> Workspace
# ---------------------------------------------------------------------------
def _managed_workspace(label: str):
	name = frappe.db.get_value(
		"Workspace", {"app": MANAGED_APP, "label": label}, "name"
	)
	if name:
		return frappe.get_doc("Workspace", name)
	ws = frappe.new_doc("Workspace")
	ws.label = label
	return ws


def sync_workspace(doc) -> None:
	"""Create/update the role-gated Workspace link for a config doc."""
	ws = _managed_workspace(doc.label)
	ws.label = doc.label
	ws.title = doc.label
	ws.public = 1
	ws.module = None  # role-only gating (see MANAGED_APP note)
	ws.app = MANAGED_APP
	ws.icon = "dashboard-list"
	ws.type = "URL"
	ws.external_link = _viewer_url(doc.dashboard)
	ws.is_hidden = 0
	if not ws.content:
		ws.content = "[]"

	# Per-item role visibility, enforced natively by Frappe.
	ws.set("roles", [])
	for row in doc.roles:
		ws.append("roles", {"role": row.role})

	ws.flags.ignore_permissions = True
	ws.flags.ignore_links = True
	ws.flags.ignore_mandatory = True
	if ws.is_new():
		ws.insert(ignore_permissions=True)
	else:
		ws.save(ignore_permissions=True)


def remove_workspace(label: str) -> None:
	name = frappe.db.get_value(
		"Workspace", {"app": MANAGED_APP, "label": label}, "name"
	)
	if name:
		frappe.delete_doc("Workspace", name, ignore_permissions=True, force=True)


# ---------------------------------------------------------------------------
# Bulk helpers (toggling the mode on/off)
# ---------------------------------------------------------------------------
def rebuild_workspaces() -> None:
	"""Drop all managed Workspaces and recreate them from enabled configs."""
	clear_managed_workspaces()
	for name in frappe.get_all("Insights Sidebar Config", {"enabled": 1}, pluck="name"):
		sync_workspace(frappe.get_doc("Insights Sidebar Config", name))
	frappe.db.commit()


def clear_managed_workspaces() -> None:
	for name in frappe.get_all("Workspace", {"app": MANAGED_APP}, pluck="name"):
		frappe.delete_doc("Workspace", name, ignore_permissions=True, force=True)
	frappe.db.commit()
