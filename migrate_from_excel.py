"""
One-time import: reads items_orders_tracker.xlsx and loads its data into the
Postgres database pointed to by DATABASE_URL.

Usage:
    pip install openpyxl psycopg2-binary
    export DATABASE_URL="postgres://user:pass@host/db"
    python migrate_from_excel.py path/to/items_orders_tracker.xlsx

Run schema.sql against the database BEFORE running this script.
Safe to re-run: existing rows are matched by their natural key (name / order
code) and updated rather than duplicated.
"""
import os
import sys

import openpyxl
import psycopg2


def header_map(ws):
    """Map header text -> column index (0-based), reading row 1."""
    first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    return {str(h).strip(): i for i, h in enumerate(first_row) if h}


def get(row, colmap, *names, default=None):
    """Return row[colmap[name]] for the first name that exists in colmap."""
    for name in names:
        if name in colmap and colmap[name] < len(row):
            val = row[colmap[name]]
            if val is not None:
                return val
    return default


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_from_excel.py path/to/workbook.xlsx")
        sys.exit(1)

    xlsx_path = sys.argv[1]
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Set DATABASE_URL first.")
        sys.exit(1)

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    conn = psycopg2.connect(database_url, sslmode="require")
    cur = conn.cursor()

    # --- Items (sheet is optional — some working copies drop it) --------
    n = 0
    if "Items" in wb.sheetnames:
        ws = wb["Items"]
        cols = header_map(ws)
        for row in ws.iter_rows(min_row=2, values_only=True):
            name = get(row, cols, "Item Name")
            category = get(row, cols, "Category")
            if not name:
                continue
            cur.execute(
                """INSERT INTO items (name, category) VALUES (%s, %s)
                   ON CONFLICT (name) DO UPDATE SET category = EXCLUDED.category""",
                (name, category),
            )
            n += 1
    else:
        print("(No 'Items' sheet found — skipping. You can add items later in the app.)")
    print(f"Items: {n} rows")

    # --- Settings: Order Categories + Order Locations -------------------
    # These two mini-tables sit one below the other on the Settings sheet,
    # so we scan for their header rows rather than assuming fixed rows.
    if "Settings" in wb.sheetnames:
        ws = wb["Settings"]
        rows = list(ws.iter_rows(values_only=True))
        cat_n = loc_n = 0
        i = 0
        while i < len(rows):
            row = rows[i]
            if row and row[0] == "Category" and (len(row) < 2 or row[1] == "Status"):
                j = i + 1
                while j < len(rows) and rows[j] and rows[j][0] and rows[j][0] not in ("Order Locations",):
                    name, status = rows[j][0], (rows[j][1] if len(rows[j]) > 1 else None)
                    cur.execute(
                        """INSERT INTO order_categories (name, status) VALUES (%s, %s)
                           ON CONFLICT (name) DO UPDATE SET status = EXCLUDED.status""",
                        (name, status or "Limited"),
                    )
                    cat_n += 1
                    j += 1
            if row and row[0] == "Location":
                j = i + 1
                while j < len(rows) and rows[j] and rows[j][0]:
                    cur.execute(
                        "INSERT INTO order_locations (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (rows[j][0],),
                    )
                    loc_n += 1
                    j += 1
            i += 1
        print(f"Order categories: {cat_n} rows, Order locations: {loc_n} rows")

    # --- Orders ----------------------------------------------------------
    ws = wb["Orders"]
    cols = header_map(ws)
    order_ids = {}  # order_code -> db id
    n = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        order_code = get(row, cols, "Order ID", "Order Code")
        if not order_code or not str(order_code).strip():
            continue
        category = get(row, cols, "Category")
        location = get(row, cols, "Location")
        cur.execute(
            """INSERT INTO orders (order_code, category, location) VALUES (%s, %s, %s)
               ON CONFLICT (order_code) DO UPDATE SET category = EXCLUDED.category, location = EXCLUDED.location
               RETURNING id""",
            (order_code, category or None, location or None),
        )
        order_ids[order_code] = cur.fetchone()[0]
        n += 1
    print(f"Orders: {n} rows")

    # --- Order Lines -------------------------------------------------------
    # Reads by header name, so it doesn't matter if a particular copy of the
    # sheet has extra/missing columns (e.g. Location or Availability moved
    # here instead of living on Orders) — only the columns our schema uses
    # are pulled in; anything else is ignored.
    ws = wb["Order Lines"]
    cols = header_map(ws)
    n = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        order_code = get(row, cols, "Order ID")
        if not order_code:
            continue
        order_date = get(row, cols, "Date", "Order Date")
        item_name = get(row, cols, "Item Name")
        unit_price = get(row, cols, "Unit Price", default=0)
        quantity = get(row, cols, "Quantity", default=0)
        if order_code not in order_ids:
            continue
        if hasattr(order_date, "date"):
            order_date = order_date.date()
        cur.execute(
            """INSERT INTO order_lines (order_id, item_name, order_date, unit_price, quantity)
               VALUES (%s, %s, %s, %s, %s)""",
            (order_ids[order_code], item_name, order_date, unit_price or 0, quantity or 0),
        )
        n += 1
    print(f"Order lines: {n} rows")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
