# Items & Orders Tracker (web app)

A small full-stack app that replaces the spreadsheet: a Python (FastAPI)
backend backed by a real Postgres database, and a plain HTML/JS frontend,
deployable to Vercel so anyone with the link can view and edit the data.

```
webapp/
├── api/index.py           FastAPI backend (all the /api/... endpoints + login gate)
├── frontend/              Frontend (index.html, app.js, styles.css) — served by the backend
├── schema.sql             Database schema — run this once
├── migrate_from_excel.py  One-time import of your existing spreadsheet
├── requirements.txt       Python dependencies
├── vercel.json            Bundles frontend/ into the function
└── source_spreadsheet.xlsx  Your uploaded file, kept for the import step
```

## 1. Create the database

Vercel's built-in Postgres option is a Neon database from the Vercel
Marketplace, which is the easiest path since it wires itself up automatically:

1. Push this project to a GitHub repo (see step 3) and import it into Vercel,
   **or** open an existing Vercel project.
2. In the project's **Storage** tab, choose **Neon Postgres** (via the
   Marketplace) and create a database. Vercel automatically adds a
   `DATABASE_URL` environment variable to your project — you don't set this
   by hand.
3. Pull that variable down locally so the next steps can use it:
   ```bash
   npm i -g vercel      # if you don't have the CLI yet
   vercel link
   vercel env pull .env.local
   ```
   Then load it into your shell: `export $(grep DATABASE_URL .env.local)`

(Any other Postgres host — Supabase, Railway, your own server — works too;
just set `DATABASE_URL` to its connection string.)

## 2. Load the schema and your existing data

```bash
pip install openpyxl psycopg2-binary
psql "$DATABASE_URL" -f schema.sql
python migrate_from_excel.py source_spreadsheet.xlsx
```

The migration script is safe to re-run — items, categories, and locations are
matched by name and updated rather than duplicated.

## 3. Deploy to Vercel

```bash
cd webapp
vercel        # first run links/creates the project and deploys a preview
vercel --prod # promotes to your production URL
```

Vercel detects the FastAPI app in `api/index.py` automatically — no build
step needed. `vercel.json` just tells it to bundle the `frontend/` folder
into the function so `FileResponse` can find those files at runtime (they're
deliberately **not** in a folder called `public/`, since Vercel serves that
one straight from its CDN, bypassing the login gate below).

If you'd rather deploy from GitHub: push this folder to a repo, then
**Import Project** at vercel.com/new. Every `git push` redeploys automatically.

## 4. Restrict who can access it

The whole app — the page itself and the API — sits behind a single login
gate (HTTP Basic Auth), controlled by one environment variable:

```
ALLOWED_USERS="you:your-password,alex:alex-password,sam:sam-password"
```

Set this in Vercel's project **Settings → Environment Variables**. Each
`username:password` pair is one person you're letting in — add yourself and
anyone else, comma-separated. Nobody else can load the page or call the API;
if the variable is empty or unset, the app denies everyone (fails closed)
rather than opening up by accident.

To add or remove someone later, just edit the `ALLOWED_USERS` value and
redeploy (or use `vercel env add/rm ALLOWED_USERS`) — no code changes needed.
Anyone you list gets full view + edit access; this doesn't have separate
per-person permission levels.

The first time someone opens the site, their browser will show a native
username/password prompt. Once entered, the browser remembers it for the
session and sends it automatically with every request — no separate login
form needed.

## Notes

- The frontend is plain JavaScript (no build step) so there's nothing to
  compile — it calls the API directly with `fetch`.
- Multiple people editing at once will all see the same data, since it's a
  shared Postgres database rather than a file.
- Table edits save on blur/change (each cell is a live input); deletions ask
  for confirmation first.
- The "Orders" list shows Date/# Lines/Total computed live from `orders_view`
  in `schema.sql` — the same MIN/COUNT/SUM logic the spreadsheet used.
- Passwords in `ALLOWED_USERS` are plain text in an env var — fine for a
  small trusted group, but not a substitute for a real auth system if this
  ever needs finer-grained roles or public sign-up.
