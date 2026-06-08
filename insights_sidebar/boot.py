# Copyright (c) 2026, Naveenkumar Hulimani and contributors
# For license information, please see license.txt

import frappe

from insights_sidebar.workspace_sync import use_workspace_mode


def boot_session(bootinfo):
	"""Expose the injection mode to the Desk client.

	When workspace mode is on, the JS bundle skips DOM injection (the items
	come from native Workspace documents instead).
	"""
	bootinfo.insights_sidebar_use_workspace = use_workspace_mode()
