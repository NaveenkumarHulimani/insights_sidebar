// Copyright (c) 2026, Univision Technocon and contributors
// For license information, please see license.txt
//
// In-place Insights viewer.
//
// A single Desk Page (route: `insights-viewer`) that renders the selected
// Insights dashboard inside an <iframe>. Navigation happens through
// `frappe.set_route('insights-viewer', <dashboard>)`, so there is no full
// browser reload and no new tab - the Desk sidebar stays visible and the
// active item stays highlighted.

frappe.pages["insights-viewer"].on_page_load = function (wrapper) {
	frappe.insights_viewer = new InsightsViewer(wrapper);
};

frappe.pages["insights-viewer"].on_page_show = function () {
	// Runs on every navigation into the page (including dashboard -> dashboard
	// switches, which do not reload the page), so we (re)load here.
	frappe.insights_viewer && frappe.insights_viewer.load_from_route();
};

class InsightsViewer {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Insights"),
			single_column: true, // keep the main Desk sidebar visible
		});

		this.$wrapper = $(wrapper);
		this.$wrapper.addClass("insights-viewer-page");

		// The page body becomes a flush, full-height frame container so the
		// embedded dashboard looks native to the Desk.
		this.$body = $(this.page.main).empty().addClass("insights-viewer-body");

		this.$frame_wrap = $('<div class="insights-frame-wrap"></div>').appendTo(this.$body);
		this.$iframe = $(
			'<iframe class="insights-frame" frameborder="0" ' +
				'allow="fullscreen; clipboard-read; clipboard-write" ' +
				'referrerpolicy="same-origin"></iframe>'
		).appendTo(this.$frame_wrap);

		this.setup_states();
		this.setup_refresh_button();
		this.bind_resize();
	}

	setup_states() {
		// Loading overlay shown until the iframe fires `load`.
		this.$loading = $(
			`<div class="insights-frame-overlay">
				<div class="insights-frame-spinner">${frappe.utils.icon("refresh", "lg")}</div>
				<div class="text-muted">${__("Loading dashboard…")}</div>
			</div>`
		).appendTo(this.$frame_wrap);

		this.$iframe.on("load", () => this.$loading.addClass("hidden"));
	}

	setup_refresh_button() {
		this.page.set_secondary_action(
			__("Refresh"),
			() => {
				if (this.current_url) {
					this.$loading.removeClass("hidden");
					this.$iframe.attr("src", this.current_url);
				}
			},
			"refresh"
		);
	}

	bind_resize() {
		// The frame fills the viewport below the navbar; recompute on resize.
		this._resize = frappe.utils.debounce(() => this.fit_height(), 100);
		$(window).on("resize.insights_viewer", this._resize);
		this.fit_height();
	}

	fit_height() {
		const top = this.$frame_wrap.offset() ? this.$frame_wrap.offset().top : 0;
		const h = Math.max(360, $(window).height() - top);
		this.$frame_wrap.css("height", h + "px");
	}

	load_from_route() {
		const route = frappe.get_route(); // ["insights-viewer", <dashboard?>]
		const dashboard = route[1] ? decodeURIComponent(route[1]) : null;

		this.fit_height();
		this.highlight_sidebar_item(dashboard);
		this.hide_messages(); // clear any previous empty/error overlay

		if (!dashboard) {
			return this.show_empty_state();
		}

		// Server-side validated: the URL is only returned if the current user
		// passes has_permission on the dashboard.
		frappe.call({
			method: "insights_sidebar.api.get_dashboard_view",
			args: { dashboard },
			freeze: false,
			callback: (r) => {
				if (!r || !r.message) return;
				const view = r.message;
				this.page.set_title(view.title || __("Insights"));
				this.current_url = view.url;
				this.$loading.removeClass("hidden");
				this.$iframe.attr("src", view.url);
			},
			error: (xhr) => this.show_error(xhr, dashboard),
		});
	}

	hide_messages() {
		this.$empty && this.$empty.addClass("hidden");
		this.$error && this.$error.addClass("hidden");
	}

	show_empty_state() {
		this.page.set_title(__("Insights"));
		this.current_url = null;
		this.$iframe.attr("src", "about:blank");
		this.$loading.addClass("hidden");
		if (!this.$empty) {
			this.$empty = $(
				`<div class="insights-frame-message">
					<p>${__("Select an Insights dashboard from the sidebar to view it here.")}</p>
				</div>`
			).appendTo(this.$frame_wrap);
		}
		this.$empty.removeClass("hidden");
	}

	show_error(xhr, dashboard) {
		this.$loading.addClass("hidden");
		const permission = xhr && xhr.responseJSON && xhr.responseJSON.exc_type === "PermissionError";
		const msg = permission
			? __("You are not permitted to view this dashboard.")
			: __("Could not load dashboard {0}.", [frappe.utils.escape_html(dashboard)]);
		this.$iframe.attr("src", "about:blank");
		if (!this.$error) {
			this.$error = $('<div class="insights-frame-message"></div>').appendTo(this.$frame_wrap);
		}
		this.$error.html(`<p>${msg}</p>`).removeClass("hidden");
	}

	highlight_sidebar_item(dashboard) {
		// Defer to the shared sidebar helper installed by the app bundle so the
		// correct `.standard-sidebar-item` gets the `active-sidebar` class.
		if (frappe.insights_sidebar && frappe.insights_sidebar.set_active) {
			frappe.insights_sidebar.set_active(dashboard);
		}
	}
}
