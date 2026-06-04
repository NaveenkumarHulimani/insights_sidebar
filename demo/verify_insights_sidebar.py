import frappe

frappe.init(site="dry-run-site")
frappe.connect()

print("=" * 60)
print("DOCTYPE EXISTS:", frappe.db.exists("DocType", "Insights Sidebar Config"))
print("LINK TARGET EXISTS:", frappe.db.exists("DocType", "Insights Dashboard"))


def ensure_role(name):
    if not frappe.db.exists("Role", name):
        frappe.get_doc({"doctype": "Role", "role_name": name}).insert(ignore_permissions=True)


def ensure_user(email, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc({
            "doctype": "User", "email": email,
            "first_name": email.split("@")[0], "send_welcome_email": 0, "enabled": 1,
        }).insert(ignore_permissions=True)
    u = frappe.get_doc("User", email)
    have = {r.role for r in u.roles}
    for r in roles:
        if r not in have:
            u.append("roles", {"role": r})
    u.save(ignore_permissions=True)


# 1) sample dashboard ------------------------------------------------------
dash = frappe.db.get_value("Insights Dashboard", {"title": "Sales Overview"}, "name")
if not dash:
    dash = frappe.get_doc({"doctype": "Insights Dashboard", "title": "Sales Overview"}).insert(
        ignore_permissions=True
    ).name
print("SAMPLE DASHBOARD:", dash)

# 2) roles + users ---------------------------------------------------------
ensure_role("Insights User")
ensure_user("viewer@example.com", ["Insights User"])
ensure_user("noaccess@example.com", [])

# 3) sidebar config --------------------------------------------------------
cfg = frappe.db.get_value("Insights Sidebar Config", {"label": "Sales Overview"}, "name")
if not cfg:
    cfg = frappe.get_doc({
        "doctype": "Insights Sidebar Config",
        "label": "Sales Overview",
        "dashboard": dash,
        "enabled": 1,
        "roles": [{"role": "Insights User"}],
    }).insert(ignore_permissions=True).name
else:
    doc = frappe.get_doc("Insights Sidebar Config", cfg)
    doc.dashboard = dash
    doc.save(ignore_permissions=True)
print("SIDEBAR CONFIG:", cfg)
frappe.db.commit()

from insights_sidebar import api

print("=" * 60)
print("ROLE-BASED VISIBILITY (get_sidebar_links):")
for u in ("viewer@example.com", "noaccess@example.com"):
    frappe.set_user(u)
    links = api.get_sidebar_links()
    print(f"  {u:24s} roles={sorted(set(frappe.get_roles()) & {'Insights User'})!s:18s} -> {[l['label'] for l in links]}")
frappe.set_user("Administrator")

print("=" * 60)
print("PERMISSION GATE (get_dashboard_view):")
frappe.set_user("viewer@example.com")
try:
    v = api.get_dashboard_view(dash)
    print("  viewer@example.com   -> OK   url=%s title=%s" % (v["url"], v["title"]))
except Exception as e:
    print("  viewer@example.com   -> ERR  %s: %s" % (type(e).__name__, e))
frappe.set_user("noaccess@example.com")
try:
    v = api.get_dashboard_view(dash)
    print("  noaccess@example.com -> GOT (UNEXPECTED!) %s" % v)
except Exception as e:
    print("  noaccess@example.com -> BLOCKED (%s) [correct]" % type(e).__name__)
frappe.set_user("Administrator")

print("=" * 60)
print("CACHE INVALIDATION:")
api.get_sidebar_links()
print("  cache populated after read :", api.get_cached_links() is not None and frappe.cache().get_value(api.SIDEBAR_CACHE_KEY) is not None)
doc = frappe.get_doc("Insights Sidebar Config", cfg)
doc.save(ignore_permissions=True)  # on_update -> clear_cache()
print("  cache cleared after save   :", frappe.cache().get_value(api.SIDEBAR_CACHE_KEY) is None)

print("=" * 60)
print("EMBED URL:", api.get_dashboard_url(dash))
frappe.destroy()
print("DONE")
