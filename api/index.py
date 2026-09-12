import os
import secrets
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ------------------------------------------------------------------ auth ---
# Access is limited to the people listed in ALLOWED_USERS, an env var of
# comma-separated "username:password" pairs, e.g.:
#   ALLOWED_USERS="jordan:hunter22,sam:tigerlily9"
# Add yourself and anyone else you want to have access; leave everyone else
# out. Set this in your Vercel project's Environment Variables.
security = HTTPBasic()


def _load_allowed_users() -> dict:
    raw = os.environ.get("ALLOWED_USERS", "")
    pairs = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        user, pw = chunk.split(":", 1)
        pairs[user.strip()] = pw.strip()
    return pairs


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    allowed = _load_allowed_users()
    if not allowed:
        # Fail closed: with nothing configured, nobody gets in (rather than
        # accidentally leaving the app open to everyone).
        raise HTTPException(500, "No ALLOWED_USERS configured on the server yet.")
    expected_pw = allowed.get(credentials.username)
    ok = expected_pw is not None and secrets.compare_digest(credentials.password, expected_pw)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# Every route below requires auth — applied once at the app level so nothing
# is accidentally left open.
app = FastAPI(title="Items & Orders Tracker API", dependencies=[Depends(require_auth)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL")


# ------------------------------------------------------------- frontend ---
# Served from here (not from a Vercel `public/` folder) so the same auth
# gate above covers the page itself, not just the /api calls.
@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def serve_js():
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
def serve_css():
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise HTTPException(500, "DATABASE_URL is not set on the server.")
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql, params=None, fetch="all"):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row else None
            return None


# ---------------------------------------------------------------- models ---
class Item(BaseModel):
    name: str
    category: Optional[str] = None


class OrderCategory(BaseModel):
    name: str
    status: str = "Limited"  # "Limited" | "Always Active"


class OrderLocation(BaseModel):
    name: str


class Order(BaseModel):
    order_code: str
    category: Optional[str] = None
    location: Optional[str] = None


class OrderLine(BaseModel):
    order_id: int
    item_name: Optional[str] = None
    order_date: Optional[date] = None
    unit_price: float = 0
    quantity: int = 1


# ----------------------------------------------------------------- items ---
@app.get("/api/items")
def list_items():
    return query("SELECT * FROM items ORDER BY name")


@app.post("/api/items")
def create_item(item: Item):
    return query(
        "INSERT INTO items (name, category) VALUES (%s, %s) RETURNING *",
        (item.name, item.category),
        fetch="one",
    )


@app.put("/api/items/{item_id}")
def update_item(item_id: int, item: Item):
    row = query(
        "UPDATE items SET name = %s, category = %s WHERE id = %s RETURNING *",
        (item.name, item.category, item_id),
        fetch="one",
    )
    if not row:
        raise HTTPException(404, "Item not found")
    return row


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    query("DELETE FROM items WHERE id = %s", (item_id,), fetch=None)
    return {"ok": True}


# ------------------------------------------------------------ categories ---
@app.get("/api/categories")
def list_categories():
    return query("SELECT * FROM order_categories ORDER BY name")


@app.post("/api/categories")
def create_category(cat: OrderCategory):
    return query(
        "INSERT INTO order_categories (name, status) VALUES (%s, %s) RETURNING *",
        (cat.name, cat.status),
        fetch="one",
    )


@app.put("/api/categories/{cat_id}")
def update_category(cat_id: int, cat: OrderCategory):
    row = query(
        "UPDATE order_categories SET name = %s, status = %s WHERE id = %s RETURNING *",
        (cat.name, cat.status, cat_id),
        fetch="one",
    )
    if not row:
        raise HTTPException(404, "Category not found")
    return row


@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: int):
    query("DELETE FROM order_categories WHERE id = %s", (cat_id,), fetch=None)
    return {"ok": True}


# ------------------------------------------------------------- locations ---
@app.get("/api/locations")
def list_locations():
    return query("SELECT * FROM order_locations ORDER BY name")


@app.post("/api/locations")
def create_location(loc: OrderLocation):
    return query(
        "INSERT INTO order_locations (name) VALUES (%s) RETURNING *",
        (loc.name,),
        fetch="one",
    )


@app.delete("/api/locations/{loc_id}")
def delete_location(loc_id: int):
    query("DELETE FROM order_locations WHERE id = %s", (loc_id,), fetch=None)
    return {"ok": True}


# ----------------------------------------------------------------- orders ---
@app.get("/api/orders")
def list_orders(
    category: Optional[str] = None,
    location: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    sql = "SELECT * FROM orders_view WHERE 1=1"
    params = []
    if category:
        sql += " AND category = %s"
        params.append(category)
    if location:
        sql += " AND location = %s"
        params.append(location)
    if date_from:
        sql += " AND order_date >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND order_date <= %s"
        params.append(date_to)
    sql += " ORDER BY order_date NULLS LAST, order_code"
    return query(sql, params)


@app.post("/api/orders")
def create_order(order: Order):
    return query(
        "INSERT INTO orders (order_code, category, location) VALUES (%s, %s, %s) RETURNING *",
        (order.order_code, order.category, order.location),
        fetch="one",
    )


@app.put("/api/orders/{order_id}")
def update_order(order_id: int, order: Order):
    row = query(
        "UPDATE orders SET order_code = %s, category = %s, location = %s WHERE id = %s RETURNING *",
        (order.order_code, order.category, order.location, order_id),
        fetch="one",
    )
    if not row:
        raise HTTPException(404, "Order not found")
    return row


@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int):
    query("DELETE FROM orders WHERE id = %s", (order_id,), fetch=None)
    return {"ok": True}


# ------------------------------------------------------------ order lines ---
@app.get("/api/order_lines")
def list_order_lines(order_id: Optional[int] = None):
    sql = """
        SELECT ol.*, i.category AS item_type
        FROM order_lines ol
        LEFT JOIN items i ON i.name = ol.item_name
    """
    params = []
    if order_id is not None:
        sql += " WHERE ol.order_id = %s"
        params.append(order_id)
    sql += " ORDER BY ol.order_date NULLS LAST, ol.id"
    return query(sql, params)


@app.post("/api/order_lines")
def create_order_line(line: OrderLine):
    return query(
        """INSERT INTO order_lines (order_id, item_name, order_date, unit_price, quantity)
           VALUES (%s, %s, %s, %s, %s) RETURNING *""",
        (line.order_id, line.item_name, line.order_date, line.unit_price, line.quantity),
        fetch="one",
    )


@app.put("/api/order_lines/{line_id}")
def update_order_line(line_id: int, line: OrderLine):
    row = query(
        """UPDATE order_lines
           SET order_id = %s, item_name = %s, order_date = %s, unit_price = %s, quantity = %s
           WHERE id = %s RETURNING *""",
        (line.order_id, line.item_name, line.order_date, line.unit_price, line.quantity, line_id),
        fetch="one",
    )
    if not row:
        raise HTTPException(404, "Order line not found")
    return row


@app.delete("/api/order_lines/{line_id}")
def delete_order_line(line_id: int):
    query("DELETE FROM order_lines WHERE id = %s", (line_id,), fetch=None)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True, "database_configured": bool(DATABASE_URL)}
