"""Create a rich, populated Insights v3 dashboard on dummy data.

 * writes ~600 recent-dated rows into a `sales` table in the demo DuckDB,
 * registers it as an Insights Table v3,
 * builds a workbook (named KPI cards + Donut/Bar/Line charts) and imports it,
 * points the "Order Analysis" sidebar config at the new dashboard.
"""

import os
import random
from datetime import date, timedelta

os.environ["CI"] = "1"

import duckdb
import frappe

frappe.init("dry-run-site")
frappe.connect()
frappe.set_user("Administrator")

random.seed(42)

# ---------------------------------------------------------------- dummy data
DB = frappe.get_site_path("private", "files", "insights_demo_data.duckdb")
regions = ["North", "South", "East", "West", "Central"]
categories = ["Electronics", "Clothing", "Home & Kitchen", "Sports", "Books"]
products = {
    "Electronics": ["Laptop", "Headphones", "Smartphone", "Monitor"],
    "Clothing": ["T-Shirt", "Jeans", "Jacket", "Sneakers"],
    "Home & Kitchen": ["Blender", "Cookware Set", "Lamp", "Vacuum"],
    "Sports": ["Yoga Mat", "Dumbbells", "Bicycle", "Tent"],
    "Books": ["Novel", "Cookbook", "Biography", "Textbook"],
}
statuses = ["Completed", "Completed", "Completed", "Pending", "Cancelled", "Refunded"]
today = date(2026, 6, 4)

rows = []
for i in range(600):
    d = today - timedelta(days=random.randint(0, 364))
    cat = random.choice(categories)
    prod = random.choice(products[cat])
    qty = random.randint(1, 8)
    unit = round(random.uniform(15, 950), 2)
    rows.append((
        f"ORD-{1000 + i}",
        d.isoformat(),
        random.choice(regions),
        cat,
        prod,
        random.choice(statuses),
        qty,
        round(unit * qty, 2),
    ))

con = duckdb.connect(DB)
con.execute("DROP TABLE IF EXISTS sales")
con.execute(
    """CREATE TABLE sales (
        order_id VARCHAR, sale_date DATE, region VARCHAR, category VARCHAR,
        product VARCHAR, status VARCHAR, quantity INTEGER, amount DOUBLE)"""
)
con.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?)", rows)
n = con.execute("SELECT count(*), round(sum(amount)) FROM sales").fetchone()
con.close()
print(f"dummy data: {n[0]} rows, total amount ~{n[1]}")

# ------------------------------------------------ register table in Insights
ds = frappe.get_doc("Insights Data Source v3", "demo_data")
ds.update_table_list()
ds.save(ignore_permissions=True)
frappe.db.commit()
print("sales table registered:", frappe.db.exists("Insights Table v3", {"data_source": "demo_data", "table": "sales"}))


# ------------------------------------------------------------- build helpers
def measure(agg, col, dtype, name):
    val = "count(*)" if agg == "count" else f"{agg}({col})"
    return {"aggregation": agg, "column_name": col, "data_type": dtype,
            "label": val, "measure_name": name, "value": val}


def dim(col, dtype, granularity=None):
    d = {"column_name": col, "data_type": dtype, "dimension_name": col,
         "label": col, "value": col}
    if granularity:
        d["granularity"] = granularity
    return d


Q = "q_sales"
charts = {}

# KPI / Number card with 4 named metrics (no period comparison -> real totals)
charts["c_kpi"] = {
    "name": "c_kpi", "title": "Key Metrics", "workbook": "", "folder": None,
    "sort_order": 0, "query": Q, "chart_type": "Number",
    "config": {
        "comparison": False, "decimal": "2",
        "filters": {"filters": [], "logical_operator": "And"}, "limit": 100,
        "negative_is_better": False, "number_column": [], "number_column_options": [],
        "number_columns": [
            measure("sum", "amount", "Decimal", "Total Revenue"),
            measure("count", "order_id", "String", "Total Orders"),
            measure("sum", "quantity", "Integer", "Units Sold"),
            measure("avg", "amount", "Decimal", "Avg Order Value"),
        ],
    },
}

# Donut: revenue by category
charts["c_donut"] = {
    "name": "c_donut", "title": "Revenue by Category", "workbook": "", "folder": None,
    "sort_order": 1, "query": Q, "chart_type": "Donut",
    "config": {
        "filters": {"filters": [], "logical_operator": "And"},
        "label_column": dim("category", "String"),
        "legend_position": "bottom", "limit": 100, "order_by": [],
        "value_column": {"aggregation": "sum", "column_name": "amount",
                         "data_type": "Decimal", "measure_name": "sum_of_amount"},
    },
}

# Bar: revenue by region
charts["c_bar"] = {
    "name": "c_bar", "title": "Revenue by Region", "workbook": "", "folder": None,
    "sort_order": 2, "query": Q, "chart_type": "Bar",
    "config": {
        "filters": {"filters": [], "logical_operator": "And"}, "grouping": "stacked",
        "limit": "100", "normalize": False, "order_by": [], "show_data_labels": False,
        "split_by": {"column_name": "", "data_type": "String", "dimension": {},
                     "dimension_name": "", "max_split_values": 10},
        "stack": False, "swap_axes": False,
        "x_axis": {"dimension": dim("region", "String")},
        "y2_axis": None, "y2_axis_type": "line",
        "y_axis": {"normalize": False, "series": [{"measure": measure("sum", "amount", "Decimal", "Revenue")}],
                   "show_axis_label": False, "show_data_labels": False, "stack": False},
    },
}

# Line: revenue by month
charts["c_line"] = {
    "name": "c_line", "title": "Revenue Trend (Monthly)", "workbook": "", "folder": None,
    "sort_order": 3, "query": Q, "chart_type": "Line",
    "config": {
        "filters": {"filters": [], "logical_operator": "And"}, "limit": "100",
        "normalize": False,
        "order_by": [{"column": {"column_name": "sale_date", "type": "column"}, "direction": "asc"}],
        "show_data_labels": False,
        "split_by": {"column_name": "", "data_type": "String", "dimension": {},
                     "dimension_name": "", "max_split_values": 10},
        "smooth": True, "swap_axes": False,
        "x_axis": {"dimension": dim("sale_date", "Datetime", "month")},
        "y2_axis": None, "y2_axis_type": "line",
        "y_axis": {"normalize": False, "series": [{"measure": measure("sum", "amount", "Decimal", "Revenue")}],
                   "show_axis_label": False, "show_data_labels": False, "stack": False},
    },
}

# Bar: orders by status
charts["c_status"] = {
    "name": "c_status", "title": "Orders by Status", "workbook": "", "folder": None,
    "sort_order": 4, "query": Q, "chart_type": "Bar",
    "config": {
        "filters": {"filters": [], "logical_operator": "And"}, "grouping": "stacked",
        "limit": "100", "normalize": False, "order_by": [], "show_data_labels": True,
        "split_by": {"column_name": "", "data_type": "String", "dimension": {},
                     "dimension_name": "", "max_split_values": 10},
        "stack": False, "swap_axes": True,
        "x_axis": {"dimension": dim("status", "String")},
        "y2_axis": None, "y2_axis_type": "line",
        "y_axis": {"normalize": False, "series": [{"measure": measure("count", "order_id", "String", "Orders")}],
                   "show_axis_label": False, "show_data_labels": True, "stack": False},
    },
}

# ---------------------------------------------------------- dashboard layout
items = [
    {"type": "chart", "chart": "c_kpi", "layout": {"i": "it_kpi", "x": 0, "y": 0, "w": 20, "h": 3, "moved": False}},
    {"type": "chart", "chart": "c_donut", "layout": {"i": "it_donut", "x": 0, "y": 3, "w": 10, "h": 9, "moved": False}},
    {"type": "chart", "chart": "c_bar", "layout": {"i": "it_bar", "x": 10, "y": 3, "w": 10, "h": 9, "moved": False}},
    {"type": "chart", "chart": "c_line", "layout": {"i": "it_line", "x": 0, "y": 12, "w": 20, "h": 9, "moved": False}},
    {"type": "chart", "chart": "c_status", "layout": {"i": "it_status", "x": 0, "y": 21, "w": 20, "h": 8, "moved": False}},
]

export = {
    "version": 1,
    "type": "workbook",
    "name": "sales-dummy",
    "doc": {"title": "Sales Analytics"},
    "dependencies": {
        "folders": [],
        "queries": {
            Q: {
                "name": Q, "title": "Sales", "workbook": "", "folder": None, "sort_order": 0,
                "use_live_connection": 1, "is_script_query": 0, "is_builder_query": 0,
                "is_native_query": 0,
                "operations": [
                    {"type": "source", "table": {"data_source": "demo_data", "table_name": "sales", "type": "table"}},
                    {"type": "cast", "column": {"column_name": "sale_date", "type": "column"}, "data_type": "Datetime"},
                ],
            }
        },
        "charts": charts,
        "dashboards": {
            "d_sales": {
                "name": "d_sales", "title": "Sales Analytics", "workbook": "",
                "items": frappe.as_json(items),
            }
        },
    },
}

from insights.insights.doctype.insights_workbook.insights_workbook import import_workbook

# clean prior build
for wb in frappe.get_all("Insights Workbook", {"title": "Sales Analytics"}, pluck="name"):
    frappe.delete_doc("Insights Workbook", wb, force=True, ignore_permissions=True)
frappe.db.commit()

new_wb = import_workbook(export)
frappe.db.commit()
dash = frappe.get_all("Insights Dashboard v3", {"workbook": new_wb}, ["name", "title"])
print("NEW WORKBOOK:", new_wb, "DASHBOARD:", dash)

new_dash = dash[0]["name"]

# point the sidebar config at the new populated dashboard
cfg = frappe.db.get_value("Insights Sidebar Config", {"label": "Order Analysis"}, "name")
if cfg:
    doc = frappe.get_doc("Insights Sidebar Config", cfg)
    doc.dashboard = new_dash
    doc.save(ignore_permissions=True)
frappe.db.commit()
print("Sidebar config 'Order Analysis' -> dashboard", new_dash)
print("URL: /insights/dashboards/%s" % new_dash)
frappe.destroy()
print("DONE")
