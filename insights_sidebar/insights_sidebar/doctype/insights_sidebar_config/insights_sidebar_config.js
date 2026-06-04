// Copyright (c) 2026, Univision Technocon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Insights Sidebar Config", {
	refresh(frm) {
		// Quick way to preview the configured dashboard in the in-place viewer.
		if (!frm.is_new() && frm.doc.dashboard) {
			frm.add_custom_button(__("Open in Viewer"), () => {
				frappe.set_route("insights-viewer", frm.doc.dashboard);
			});
		}
	},
});
