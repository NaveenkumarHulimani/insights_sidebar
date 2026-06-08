"""Read-only backend showcase for a screen recording.

Prints a clean narrative of the server-side behaviour (role-based visibility,
the has_permission gate, and caching) against the CURRENT data - it does not
create or delete anything.

Run from the bench:
    cd ~/frappe-bench/sites
    ../env/bin/python demo/showcase_backend.py
"""

import frappe

frappe.init("dry-run-site")
frappe.connect()
frappe.set_user("Administrator")

from insights_sidebar import api

LINE = "=" * 64


def banner(t):
    print("\n" + LINE + "\n " + t + "\n" + LINE)


banner("1) CONFIGURATION DocType  (Insights Sidebar Config)")
meta = frappe.get_meta("Insights Sidebar Config")
for f in meta.fields:
    if f.fieldname in ("label", "dashboard", "roles", "enabled"):
        opt = f" -> {f.options}" if f.options else ""
        print(f"   {f.label:14s} : {f.fieldtype}{opt}")
print("\n   Records:")
for c in frappe.get_all("Insights Sidebar Config", fields=["name", "dashboard", "enabled"]):
    roles = frappe.get_all("Has Role", {"parent": c.name}, pluck="role")
    print(f"     - {c.name:18s} dashboard={c.dashboard:12s} roles={roles}")

banner("2) ROLE-BASED VISIBILITY  (cached get_sidebar_links)")
for u in ["Administrator", "viewer@example.com", "noaccess@example.com"]:
    frappe.set_user(u)
    links = [l["label"] for l in api.get_sidebar_links()]
    print(f"   {u:24s} -> {links}")
frappe.set_user("Administrator")

banner("3) SECURITY GATE  (get_dashboard_view -> has_permission)")
# Use a dashboard the viewer is actually entitled to, to show BOTH a positive
# (allowed) and a negative (blocked) result on the same dashboard.
frappe.set_user("viewer@example.com")
viewer_links = api.get_sidebar_links()
frappe.set_user("Administrator")
dash = viewer_links[0]["dashboard"] if viewer_links else \
    frappe.db.get_value("Insights Sidebar Config", {"enabled": 1}, "dashboard")
print(f"   (testing dashboard: {dash})\n")
for u in ["viewer@example.com", "noaccess@example.com"]:
    frappe.set_user(u)
    try:
        v = api.get_dashboard_view(dash)
        print(f"   {u:24s} -> ALLOWED  url={v['url']}")
    except Exception as e:
        print(f"   {u:24s} -> BLOCKED  ({type(e).__name__})  [correct]")
frappe.set_user("Administrator")

banner("4) CACHING  (no DB scan per page load)")
api.clear_cache()
print("   cache cleared, first read (builds + caches) ...")
api.get_sidebar_links()
cached = frappe.cache().get_value(api.SIDEBAR_CACHE_KEY) is not None
print(f"   cache populated after first read : {cached}")
print("   ... saving a config invalidates it (on_update -> clear_cache)")

print("\n" + LINE + "\n DONE\n" + LINE)
frappe.destroy()
