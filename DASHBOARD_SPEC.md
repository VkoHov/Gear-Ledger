# Gear Ledger — Lightweight Web Dashboard Spec

Status: **Exploratory — not started.** This is a spec for planning purposes
only. Nothing here should be implemented without an explicit go-ahead.

## Scope

This is the "middle path" recommended in [`WEB_APP_ROADMAP.md`](./WEB_APP_ROADMAP.md):
the desktop app keeps doing all scanning-workstation work (camera, scale,
TTS, matching) exactly as it does today. This dashboard is a **separate,
read-mostly web frontend** for people who need to check on or export data
without scanning anything — a sales rep checking if an order's done, an
office admin generating an invoice, anyone who'd otherwise ask "can you
just email me the numbers."

**In scope:** view results, browse catalog, check completeness, generate/
download invoices.
**Out of scope (stays desktop-only):** scanning, camera, scale, vision
matching, TTS, catalog *upload* (still done from the scanning workstation —
see Open questions).

**Hard prerequisite:** auth + multi-tenancy from `SAAS_ROADMAP.md`. Every
route below assumes a logged-in, tenant-scoped session — none of this is
buildable against the current unauthenticated `server.py`.

## Page list

| Page | Purpose | Backing routes |
|---|---|---|
| **Login** | Email/password (or magic link) → session | New, from SaaS auth work |
| **Results** | Table of all recorded matches, filterable by client; the web equivalent of the desktop results table | `GET /api/results` (exists) |
| **Client detail** (optional, could just be a filter on Results) | Same table scoped to one client | `GET /api/results?client=` (exists) |
| **Catalog** | Browse the uploaded catalog (read-only) | `GET /api/catalog/info` (exists), new `GET /api/catalog/rows` |
| **Completeness** | Ordered-vs-recorded report, same three buckets (not started / partial / over-recorded) plus not-in-catalog, as seen in the desktop completeness dialog (`main_window.py:3200`+) | New `GET /api/completeness` |
| **Invoice** | Pick a client (or "all"), a weight price, generate, download `.xlsx` | New `POST /api/invoice` |
| **Settings** (minimal) | Change password, see plan/seats — reuses SaaS-roadmap account UI, not new dashboard-specific work | SaaS auth work |

No versions/restore page — see Open questions below on why.

## Routes: what exists vs. what's new

Existing (`gearledger/server.py`), reusable almost as-is once auth
middleware wraps them:

- `GET /api/results` — returns `{ok, results: [...]}`, each row matching the
  `results` table schema (`id, artikul, client, quantity, weight,
  last_updated, brand, description, sale_price, total_price, created_at`).
  Already supports `?client=` filtering.
- `GET /api/clients` — distinct client list, for a filter dropdown.
- `GET /api/catalog/info` — filename/size/upload-time metadata.
- `GET /api/catalog` — downloads the raw catalog file (works today, but see
  the in-memory-only caveat below).

New routes needed:

- `GET /api/completeness` — thin wrapper around
  `data_layer.check_catalog_completeness(catalog_path, results_path)`,
  which already returns exactly the shape the dashboard needs
  (`not_started`, `partial`, `over_recorded`, `not_in_catalog`,
  `complete_count`, `total_count`). No new business logic — just an HTTP
  shell and the temp-file adapter described below.
- `POST /api/invoice` — wraps
  `invoice_generator.generate_invoice_from_results(results_path,
  catalog_path, output_path, weight_price)`. Accepts `{client?, weight_price}`
  in the body, returns the generated `.xlsx` as a file download. Same
  temp-file adapter as completeness.
- `GET /api/catalog/rows` — the desktop app reads the catalog via pandas
  directly wherever it needs it; there's no existing "list catalog rows as
  JSON" endpoint. New, simple: parse the in-memory catalog with the existing
  `excel_utils` loader and return rows.

### The temp-file adapter (already a proven pattern, not new risk)

Both `check_catalog_completeness` and `generate_invoice_from_results` take
**file paths**, not bytes or DB handles — they were written for the
filesystem-based desktop flow. The server, however, holds catalog data
**in memory only** (`self._catalog_data` bytes in `server.py`) and results
**in SQLite**, not as files.

This isn't a new problem to solve — `main_window.py:_on_generate_invoice_requested`
(`main_window.py:2857`-2882) already does exactly this adapter for the
desktop "server mode" case: export DB rows to a `tempfile.mkstemp(".xlsx")`
via `result_ledger.rows_to_dataframe`, pass that path in, delete the temp
file in a `finally` block. The two new routes do the same thing server-side:
DB rows → temp results file, in-memory catalog bytes → temp catalog file,
call the existing function, stream the output, clean up. No changes needed
to `invoice_generator.py` or `data_layer.py` themselves.

## Data flow

```
Browser (dashboard SPA)
  → HTTPS, session cookie/token (SaaS auth)
  → Flask API (server.py + new routes)
      → SQLite (results, per-tenant db_path)
      → in-memory catalog bytes (per-tenant; see caveat below)
      → temp-file adapter for completeness/invoice
  ← JSON (results/completeness/catalog rows) or file download (invoice/catalog)
```

No SSE/live-update needed for a first version — the dashboard is a
check-in/export tool, not a live scanning view. Polling or manual refresh
is enough; can revisit if "watch results come in live" turns out to matter.

## Caveats surfaced by reading the actual code

- **Catalog is in-memory only, per server process.** `_catalog_data` in
  `server.py` isn't persisted to disk or DB — a server restart loses it
  until the desktop app re-uploads. Fine for a single LAN server; needs a
  real decision once this is cloud-hosted and multi-tenant (persist catalog
  bytes in the tenant's DB or object storage), otherwise the dashboard's
  Catalog/Completeness/Invoice pages go blank after every deploy. This is a
  SaaS-roadmap-adjacent gap, not dashboard-specific, but the dashboard is
  what makes it visible/painful, so worth fixing alongside this work rather
  than after.
- **No "browse versions and restore" UI exists today, even on desktop.**
  `WEB_APP_ROADMAP.md`'s feature table lists "Reset / Versions / Restore" as
  a feature to port, but `archive_results_before_clear` / `restore_from_version`
  (`database.py:503`, `:550`) are only ever called automatically (on clear)
  or from the one-time legacy-migration path — there's no button in
  `main_window.py` that lists version files and lets a user pick one to
  restore. Porting "versions" to the dashboard would mean *designing* that
  UI for the first time, not porting an existing one. Recommend dropping it
  from dashboard v1 scope entirely — nothing today depends on it, and it's
  not part of the "why can't I just check this from my browser" ask.
- **Catalog upload stays desktop-only in this spec.** The scanning
  workstation is still the place a new catalog file originates; the
  dashboard only reads. If office staff need to upload catalogs without
  touching the desktop app, that's one more route (`POST /api/catalog`
  already exists and needs no changes) plus a page — cheap to add later,
  intentionally left out of v1 to keep the estimate tight.

## Effort re-estimate

Assumes the SaaS roadmap's auth/multi-tenancy is done first (its own 3–4
week estimate, unchanged).

| Piece | Effort | Notes |
|---|---|---|
| New backend routes (`/api/completeness`, `/api/invoice`, `/api/catalog/rows`) | 3–5 days | Thin wrappers per above; temp-file adapter is copy-adjacent to existing desktop code |
| Frontend: Results + Client filter page | 3–4 days | Table + filter dropdown, no new backend logic |
| Frontend: Catalog browse page | 2–3 days | Read-only table |
| Frontend: Completeness page | 3–4 days | Four-section report, mirrors the desktop dialog's grouping |
| Frontend: Invoice page | 2–3 days | Form (client, weight price) → download |
| Auth pages (login, session handling) | Shared with SaaS roadmap's auth work — not double-counted here | |
| Catalog persistence fix (in-memory → per-tenant storage) | 2–4 days | Only strictly required once cloud-hosted; can defer to just before launch |

**Total: roughly 2.5–3 weeks of frontend+backend work**, on top of the SaaS
roadmap's prerequisite auth/multi-tenancy — consistent with
`WEB_APP_ROADMAP.md`'s original "2–3 weeks" estimate for this path, now with
the specific pieces broken out.

## Open questions

- Should catalog **upload** move to the dashboard too, or stay desktop-only
  indefinitely? Affects whether "office staff never touch the desktop app"
  is fully true or just mostly true.
- Live updates (SSE) — worth it for v1, or is manual refresh acceptable
  given this is a check-in tool, not a scanning view?
- Where does the in-memory-catalog persistence fix land — bundled into this
  work, or tracked as a SaaS-roadmap item since it's really about cloud
  multi-tenancy, not the dashboard specifically?

## Related

See [`WEB_APP_ROADMAP.md`](./WEB_APP_ROADMAP.md) for the full feasibility
analysis this spec narrows down, and [`SAAS_ROADMAP.md`](./SAAS_ROADMAP.md)
for the auth/multi-tenancy prerequisite.
