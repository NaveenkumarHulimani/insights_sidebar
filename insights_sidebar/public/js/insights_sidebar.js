// Copyright (c) 2026, Naveenkumar Hulimani and contributors
// For license information, please see license.txt
//
// Desk sidebar injector.
//
// Loaded on every Desk page via `app_include_js`. It pulls the role-filtered
// Insights links from the server (cached server-side) and injects them into
// the standard Frappe sidebar (`.body-sidebar .sidebar-items`) using the same
// markup Frappe itself uses, so the items look native.
//
// v16 re-renders the sidebar on every workspace/route change (it empties
// `.sidebar-items`), so we re-inject through a MutationObserver and on
// router change. Clicking an item routes to the in-place viewer via
// `frappe.set_route(...)` - no full reload, no new tab - and the active item
// stays highlighted with Frappe's own `active-sidebar` class.

frappe.provide("frappe.insights_sidebar");

(function () {
	const SECTION_ID = "insights-sidebar-section";
	const VIEWER_ROUTE = "insights-viewer";
	const ITEM_CLASS = "insights-sidebar-item";
	const SECTION_CLASS = "insights-sidebar-section-header";

	let links = [];
	let observer = null;

	function sidebar_items_el() {
		return document.querySelector(".body-sidebar .sidebar-items");
	}

	function esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	function css_escape(v) {
		return window.CSS && CSS.escape ? CSS.escape(v) : String(v).replace(/"/g, '\\"');
	}

	// The Desk is usually mounted at /app, but some sites use a custom path
	// (e.g. /desk). Derive it from the current URL so the item href matches the
	// real route (needed for middle-click / native active-state matching).
	function desk_prefix() {
		const m = (window.location.pathname || "/app").match(/^\/[^/]+/);
		return m ? m[0] : "/app";
	}

	// -- data ---------------------------------------------------------------
	function fetch_links() {
		return frappe
			.xcall("insights_sidebar.api.get_sidebar_links")
			.then((result) => (links = result || []))
			.catch(() => (links = []));
	}

	// -- markup (mirrors frappe/ui/sidebar/sidebar_item.html) ---------------
	function make_section_header() {
		return $(
			`<div class="sidebar-item-container section-item ${SECTION_CLASS}" data-id="${SECTION_ID}">
				<div class="standard-sidebar-item">
					<div class="item-anchor section-break">
						<span class="sidebar-item-label">${__("Insights")}</span>
						<div class="sidebar-item-control"></div>
					</div>
				</div>
			</div>`
		);
	}

	function make_item(link) {
		const path = `${desk_prefix()}/${VIEWER_ROUTE}/${encodeURIComponent(link.dashboard)}`;
		const icon = frappe.utils.icon("dashboard-list", "md", "", "", "sidebar-item-icon");
		const $item = $(
			`<div class="sidebar-item-container ${ITEM_CLASS}"
					item-name="${esc(link.label)}"
					data-id="${esc(link.label)}"
					data-insights-dashboard="${esc(link.dashboard)}"
					title="${esc(link.label)}"
					data-toggle="tooltip" data-placement="right">
				<div class="standard-sidebar-item">
					<a href="${path}" class="item-anchor">
						<span class="sidebar-item-icon">${icon}</span>
						<span class="sidebar-item-label">${esc(link.label)}</span>
					</a>
				</div>
			</div>`
		);

		// Route within the Desk SPA - never a full reload, never a new tab.
		$item.find("a.item-anchor").on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			frappe.set_route(VIEWER_ROUTE, link.dashboard);
		});

		return $item;
	}

	// -- render -------------------------------------------------------------
	function render() {
		const el = sidebar_items_el();
		if (!el) return;
		const $items = $(el);

		// Clear any previous injection so re-render is idempotent.
		$items.find(`.${SECTION_CLASS}, .${ITEM_CLASS}`).remove();
		if (!links.length) return;

		const $frag = $(document.createDocumentFragment());
		$frag.append(make_section_header());
		links.forEach((link) => $frag.append(make_item(link)));
		$items.append($frag);

		set_active_from_route();
	}

	function ensure_observer() {
		const el = sidebar_items_el();
		if (!el || observer) return;
		observer = new MutationObserver(
			frappe.utils.debounce(() => {
				const current = sidebar_items_el();
				if (current && links.length && !current.querySelector(`.${ITEM_CLASS}`)) {
					render();
				}
			}, 50)
		);
		observer.observe(el, { childList: true });
	}

	// -- active highlight ---------------------------------------------------
	function set_active(dashboard) {
		const el = sidebar_items_el();
		if (!el) return;
		const $items = $(el);
		$items
			.find(`.${ITEM_CLASS} .standard-sidebar-item`)
			.removeClass("active-sidebar selected");
		if (!dashboard) return;
		$items
			.find(`.${ITEM_CLASS}[data-insights-dashboard="${css_escape(dashboard)}"] .standard-sidebar-item`)
			.addClass("active-sidebar selected");
	}

	function set_active_from_route() {
		const route = frappe.get_route() || [];
		if (route[0] === VIEWER_ROUTE) {
			set_active(route[1] ? decodeURIComponent(route[1]) : null);
		} else {
			set_active(null);
		}
	}

	// -- realtime (live updates without a refresh) --------------------------
	function on_item_removed(data) {
		if (!data) return;
		links = links.filter((l) => l.name !== data.name && l.dashboard !== data.dashboard);
		const el = sidebar_items_el();
		if (el) {
			$(el)
				.find(`.${ITEM_CLASS}[data-insights-dashboard="${css_escape(data.dashboard)}"]`)
				.remove();
		}
		// If the user is currently viewing the removed dashboard, let them know.
		const route = frappe.get_route() || [];
		if (route[0] === VIEWER_ROUTE && route[1] === data.dashboard) {
			frappe.show_alert(
				{ message: __("This dashboard was removed by an administrator."), indicator: "orange" },
				7
			);
		}
	}

	// Route any internal link to the viewer in-place (no reload, no new tab).
	// This also makes Workspace-mode `type=URL` links behave natively, beating
	// Frappe's target="_blank" on URL links (capture phase + preventDefault).
	function install_click_shim() {
		if (window.__insights_viewer_shim) return;
		window.__insights_viewer_shim = true;
		const re = new RegExp("/" + VIEWER_ROUTE + "/([^/?#]+)");
		document.addEventListener(
			"click",
			(e) => {
				const a = e.target.closest && e.target.closest(`a[href*="/${VIEWER_ROUTE}/"]`);
				if (!a) return;
				const m = (a.getAttribute("href") || "").match(re);
				if (!m) return;
				e.preventDefault();
				e.stopPropagation();
				frappe.set_route(VIEWER_ROUTE, decodeURIComponent(m[1]));
			},
			true
		);
	}

	// -- boot ---------------------------------------------------------------
	function init() {
		install_click_shim();

		// Workspace-document mode: native (role-gated) Workspace links provide
		// the sidebar entries, so skip DOM injection to avoid double items.
		if (frappe.boot && frappe.boot.insights_sidebar_use_workspace) {
			return;
		}

		fetch_links().then(() => {
			render();
			ensure_observer();
		});

		// v16 rebuilds the sidebar on route change; re-apply after it renders.
		frappe.router.on("change", () => setTimeout(render, 0));

		// Live updates pushed by the InsightsSidebarConfig controller.
		frappe.realtime.on("insights_sidebar_item_removed", on_item_removed);
		frappe.realtime.on("insights_sidebar_changed", () => fetch_links().then(render));
	}

	// Public hook used by the viewer page to keep the item highlighted.
	frappe.insights_sidebar = {
		set_active,
		refresh: () => fetch_links().then(render),
	};

	function boot() {
		if (sidebar_items_el()) {
			init();
		} else {
			setTimeout(boot, 200); // sidebar DOM not ready yet
		}
	}

	$(document).on("startup", boot);
	$(boot); // also try on DOM ready (covers reloads where startup already fired)
})();
