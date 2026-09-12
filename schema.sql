-- Items / Orders tracker schema (PostgreSQL)
-- Run this once against your database before using the app
-- (e.g. `psql "$DATABASE_URL" -f schema.sql`)

CREATE TABLE IF NOT EXISTS items (
    id       SERIAL PRIMARY KEY,
    name     TEXT UNIQUE NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS order_categories (
    id     SERIAL PRIMARY KEY,
    name   TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'Limited' CHECK (status IN ('Limited', 'Always Active'))
);

CREATE TABLE IF NOT EXISTS order_locations (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id         SERIAL PRIMARY KEY,
    order_code TEXT UNIQUE NOT NULL,
    category   TEXT REFERENCES order_categories(name) ON UPDATE CASCADE ON DELETE SET NULL,
    location   TEXT REFERENCES order_locations(name) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_lines (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_name  TEXT REFERENCES items(name) ON UPDATE CASCADE ON DELETE SET NULL,
    order_date DATE,
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
    quantity   INTEGER NOT NULL DEFAULT 1,
    line_total NUMERIC(14, 2) GENERATED ALWAYS AS (unit_price * quantity) STORED
);

-- One row per order, with the date/count/total rolled up from its lines —
-- the same "Orders" view the spreadsheet computed with MINIFS/COUNTIF/SUMIF.
CREATE OR REPLACE VIEW orders_view AS
SELECT
    o.id,
    o.order_code,
    o.category,
    o.location,
    MIN(ol.order_date)            AS order_date,
    COUNT(ol.id)                  AS line_count,
    COALESCE(SUM(ol.line_total), 0) AS total_price
FROM orders o
LEFT JOIN order_lines ol ON ol.order_id = o.id
GROUP BY o.id, o.order_code, o.category, o.location;

-- Seed the four order locations and the standard categories, if not already present
INSERT INTO order_locations (name) VALUES
    ('Davis'), ('Hawick'), ('Textile City'), ('Vespucci Canals')
ON CONFLICT (name) DO NOTHING;

INSERT INTO order_categories (name, status) VALUES
    ('General', 'Limited'),
    ('Vehicle', 'Limited'),
    ('Hunting', 'Limited'),
    ('All', 'Always Active')
ON CONFLICT (name) DO NOTHING;
