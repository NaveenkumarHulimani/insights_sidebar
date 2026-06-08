app_name = "insights_sidebar"
app_title = "Insights Sidebar"
app_publisher = "Naveenkumar Hulimani"
app_description = "Dynamically inject role-based Insights dashboards into the Frappe Desk sidebar, rendered in-place via an iframe."
app_email = "naveenkumarh1998@gmail.com"
app_license = "mit"
app_version = "0.0.1"

# Includes in <head>
# ------------------
# Loaded on every Desk page. This bundle injects the role-filtered Insights
# items into the standard Desk sidebar and keeps the active item highlighted.
app_include_js = "/assets/insights_sidebar/js/insights_sidebar.js"
app_include_css = "/assets/insights_sidebar/css/insights_sidebar.css"

# Boot
# ----
# Exposes the active injection mode (JS injection vs Workspace documents) to the
# Desk client so the bundle can avoid double-injecting.
extend_bootinfo = "insights_sidebar.boot.boot_session"

# Document Events
# ---------------
# NOTE: The cache-invalidation and UI-cleanup logic lives in the
# `InsightsSidebarConfig` controller (validate / on_update / after_insert /
# on_trash) as required by the assignment ("Use on_trash or after_delete
# controllers for cleanup logic"). Those lifecycle methods are invoked
# automatically by Frappe, so no doc_events registration is needed here.
