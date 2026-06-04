import os

# Use the bundled insights_demo_data.duckdb instead of downloading from Google Drive.
os.environ["CI"] = "1"

import frappe

frappe.init("dry-run-site")
frappe.connect()
frappe.set_user("Administrator")

from insights.setup.demo import DemoDataFactory

factory = DemoDataFactory.run(force=True)
frappe.db.commit()

print("=" * 60)
print("DATA SOURCES:", frappe.get_all("Insights Data Source v3", fields=["name", "title", "database_type"]))
print("WORKBOOKS:", frappe.get_all("Insights Workbook", fields=["name", "title"]))
print("V3 DASHBOARDS:", frappe.get_all("Insights Dashboard v3", fields=["name", "title", "workbook"]))
print("V3 CHARTS count:", frappe.db.count("Insights Chart v3"))
print("V3 QUERIES count:", frappe.db.count("Insights Query v3"))
print("DEMO TABLES:", frappe.db.count("Insights Table v3", {"data_source": "demo_data"}))
frappe.destroy()
print("DONE")
