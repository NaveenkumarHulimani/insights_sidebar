# Copyright (c) 2026, Naveenkumar Hulimani and contributors
# For license information, please see license.txt
"""Server-side API for the Insights Sidebar.

Responsibilities
----------------
* Build and **cache** the full set of sidebar configs so we never hit the
  database on every Desk page load (cache is invalidated by the
  ``InsightsSidebarConfig`` controller on any change).
* Filter the cached configs by the **current user's roles** and by
  ``frappe.has_permission`` on the linked dashboard.
* Expose a **server-validated** payload for the in-place iframe viewer, so a
  user can never load a dashboard they are not permitted to read - even if they
  craft the route manually.

Nothing here hardcodes a dashboard id or a role name; everything is derived
from the ``Insights Sidebar Config`` records and the linked doctype.
"""

import frappe
from frappe import _

# Cache key for the unfiltered list of enabled sidebar configs.
SIDEBAR_CACHE_KEY = "insights_sidebar_links"

# The doctype the sidebar points at. Kept as a single constant (not scattered
# string literals) and overridable via site config for non-default Insights
# deployments, so there is no hardcoding spread through the codebase.
DEFAULT_DASHBOARD_DOCTYPE = "Insights Dashboard"

# Custom Desk page that renders the in-place iframe viewer.
VIEWER_ROUTE = "insights-viewer"


def get_dashboard_doctype() -> str:
	return frappe.conf.get("insights_dashboard_doctype") or DEFAULT_DASHBOARD_DOCTYPE


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------
def _build_links() -> list[dict]:
	"""Read every *enabled* config + its roles from the database.

	This is the only place that queries the configuration tables. It runs once
	and the result is cached until a config is created/updated/deleted.
	"""
	configs = frappe.get_all(
		"Insights Sidebar Config",
		filters={"enabled": 1},
		fields=["name", "label", "dashboard"],
		order_by="label asc",
	)
	for config in configs:
		config["roles"] = frappe.get_all(
			"Has Role",
			filters={"parenttype": "Insights Sidebar Config", "parent": config["name"]},
			pluck="role",
		)
	return configs


def get_cached_links() -> list[dict]:
	"""Return the cached, unfiltered config list (builds + caches on miss)."""
	return frappe.cache().get_value(SIDEBAR_CACHE_KEY, _build_links)


def clear_cache(*args, **kwargs) -> None:
	"""Invalidate the sidebar cache. Called by the controller on any change."""
	frappe.cache().delete_value(SIDEBAR_CACHE_KEY)


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------
def _can_read_dashboard(dashboard: str | None) -> bool:
	doctype = get_dashboard_doctype()
	if not dashboard or not frappe.db.exists(doctype, dashboard):
		return False
	return bool(frappe.has_permission(doctype, "read", doc=dashboard))


# ---------------------------------------------------------------------------
# Whitelisted endpoints (called from the Desk JS)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_sidebar_links() -> list[dict]:
	"""Links the **current user** is allowed to see.

	A link is returned only when the user has at least one of the configured
	roles AND can read the linked dashboard.
	"""
	user_roles = set(frappe.get_roles())
	links: list[dict] = []

	for config in get_cached_links():
		allowed_roles = set(config.get("roles") or [])
		# Visible only to users who possess at least one of the configured roles.
		if not allowed_roles or not (user_roles & allowed_roles):
			continue
		# Defence in depth: never surface a dashboard the user cannot read.
		if not _can_read_dashboard(config["dashboard"]):
			continue

		links.append(
			{
				"name": config["name"],
				"label": config["label"],
				"dashboard": config["dashboard"],
				"route": [VIEWER_ROUTE, config["dashboard"]],
			}
		)
	return links


@frappe.whitelist()
def get_dashboard_view(dashboard: str) -> dict:
	"""Return a **server-validated** payload for the iframe viewer.

	This is the security gate for the in-place viewer: the embeddable URL is
	only returned when the current user passes ``has_permission`` on the
	dashboard. Crafting the route by hand therefore cannot expose a dashboard
	the user is not allowed to read.
	"""
	doctype = get_dashboard_doctype()

	if not dashboard or not frappe.db.exists(doctype, dashboard):
		frappe.throw(_("Dashboard {0} does not exist.").format(dashboard), frappe.DoesNotExistError)

	if not frappe.has_permission(doctype, "read", doc=dashboard):
		raise frappe.PermissionError(_("You are not permitted to view dashboard {0}.").format(dashboard))

	return {
		"dashboard": dashboard,
		"title": _dashboard_title(dashboard),
		"url": get_dashboard_url(dashboard),
	}


# ---------------------------------------------------------------------------
# URL / title builders (finalised against the installed Insights version)
# ---------------------------------------------------------------------------
def _dashboard_title(dashboard: str) -> str:
	doctype = get_dashboard_doctype()
	meta = frappe.get_meta(doctype)
	title_field = meta.get_title_field() if meta else None
	if title_field and title_field != "name":
		return frappe.db.get_value(doctype, dashboard, title_field) or dashboard
	return dashboard


def get_dashboard_url(dashboard: str) -> str:
	"""Build the embeddable Insights dashboard URL.

	Insights serves its SPA under ``/insights`` and routes a dashboard at
	``/dashboard/:name`` (see ``insights/frontend/src/router.ts``), so the
	in-Desk iframe loads ``/insights/dashboard/<name>``.

	Both the base path and the per-dashboard pattern are overridable via
	``site_config`` (``insights_dashboard_base_path`` /
	``insights_dashboard_url_pattern``) so nothing is tied to a specific
	deployment or Insights version - no hardcoding.
	"""
	base = (frappe.conf.get("insights_dashboard_base_path") or "/insights").rstrip("/")
	pattern = frappe.conf.get("insights_dashboard_url_pattern")
	if not pattern:
		# Insights v3 routes a single dashboard at /dashboards/<name> (plural),
		# v2 at /dashboard/<name> (singular). Pick based on the target doctype.
		if get_dashboard_doctype() == "Insights Dashboard v3":
			pattern = "{base}/dashboards/{name}"
		else:
			pattern = "{base}/dashboard/{name}"
	return pattern.format(base=base, name=frappe.utils.quote(dashboard))
