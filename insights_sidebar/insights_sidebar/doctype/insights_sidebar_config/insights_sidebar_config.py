# Copyright (c) 2026, Univision Technocon and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from insights_sidebar.api import VIEWER_ROUTE, clear_cache, get_dashboard_doctype
from insights_sidebar import workspace_sync

# Realtime events the Desk JS listens to, so open browsers update live without
# a page refresh.
EVENT_CHANGED = "insights_sidebar_changed"
EVENT_ITEM_REMOVED = "insights_sidebar_item_removed"


class InsightsSidebarConfig(Document):
	def validate(self):
		# A sidebar item with no roles would be visible to nobody; require at
		# least one so the configuration is meaningful.
		if not self.roles:
			frappe.throw(_("Please add at least one role under <b>Visible To Roles</b>."))

		# Guard against duplicate roles in the child table.
		seen = set()
		for row in self.roles:
			if row.role in seen:
				frappe.throw(_("Role {0} is added more than once.").format(frappe.bold(row.role)))
			seen.add(row.role)

		# Make sure the linked dashboard actually exists in the installed
		# Insights version (the doctype name is resolved, never hardcoded).
		doctype = get_dashboard_doctype()
		if self.dashboard and not frappe.db.exists(doctype, self.dashboard):
			frappe.throw(_("Dashboard {0} does not exist.").format(frappe.bold(self.dashboard)))

	# -- cache invalidation -------------------------------------------------
	# Any create/update must rebuild the cached link set on the next request.
	def after_insert(self):
		clear_cache()
		self._sync_workspace()
		self._notify_changed()

	def on_update(self):
		clear_cache()
		self._sync_workspace()
		self._notify_changed()

	# -- deletion cleanup ---------------------------------------------------
	def on_trash(self):
		"""Cleanup logic for deletes (assignment: use on_trash controller).

		Invalidate the cache, remove the managed Workspace (if any), and tell
		every open Desk session to programmatically remove this item from the
		sidebar UI.
		"""
		clear_cache()
		workspace_sync.remove_workspace(self.label)
		frappe.publish_realtime(
			EVENT_ITEM_REMOVED,
			{
				"name": self.name,
				"label": self.label,
				"dashboard": self.dashboard,
				"route": [VIEWER_ROUTE, self.dashboard],
			},
			after_commit=True,
		)

	# -- helpers ------------------------------------------------------------
	def _sync_workspace(self):
		"""Keep the native Workspace in sync when workspace mode is enabled."""
		if workspace_sync.use_workspace_mode():
			if self.enabled:
				workspace_sync.sync_workspace(self)
			else:
				workspace_sync.remove_workspace(self.label)

	def _notify_changed(self):
		frappe.publish_realtime(EVENT_CHANGED, {"name": self.name}, after_commit=True)
