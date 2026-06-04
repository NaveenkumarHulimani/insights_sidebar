# Demo / verification scripts

Helper scripts used to set up demo data and verify the app on a dev bench
(examples assume a site named `dry-run-site` with **Insights v3** installed). Run
them with the bench environment python from the `frappe-bench/sites` directory,
e.g.:

```bash
cd ~/frappe-bench/sites
../env/bin/python /path/to/verify_insights_sidebar.py
```

| Script | What it does |
|---|---|
| `verify_insights_sidebar.py` | Creates a sample dashboard, role, users and config, then verifies **role-based visibility**, the **`has_permission`** gate, and **cache invalidation**. |
| `run_demo.py` | Runs Insights' bundled `DemoDataFactory` (uses the local DuckDB sample) to create a demo workbook/dashboard. |
| `build_dashboard.py` | Builds a **rich, populated** dashboard on dummy data: ~600 recent-dated sales rows + named KPI cards and Donut/Bar/Line charts, imported via `import_workbook`. |

These are **not** part of the installed app — they're convenience scripts for
demonstrating and verifying behaviour.
