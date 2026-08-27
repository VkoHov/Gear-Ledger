# Gear Ledger — Path to a Business (SaaS Roadmap)

Status: **Exploratory — not started.** This document captures a planning
discussion, not a committed plan. Nothing here should be implemented
without an explicit go-ahead.

## The problem today

Gear Ledger currently works entirely on a local network: one PC runs
"server mode" (Flask + SQLite), other PCs run "client mode" and discover
the server via UDP broadcast on the LAN. This has no user accounts, no
registration, no payment, and no way to run it as a business — there's
nothing to sell or meter.

It also has a real, recurring support cost: getting a client PC to reach
a server PC depends on that customer's specific firewall, router, and
antivirus setup. A real debugging session (2026-07) traced one such
failure through Windows Firewall block rules, Windows' Hyper-V/WSL
excluded-port-range reservations, and router client-isolation settings
before finding the actual cause. That class of problem is inherent to
requiring **inbound** connections on a customer's LAN, and would recur,
in some new form, for every new customer's environment.

## Direction: cloud-hosted server, not full rewrite

Move the server component off the customer's LAN and into the cloud.
Client machines make **outbound** HTTPS calls to a fixed domain instead
of discovering a LAN peer — this eliminates the entire inbound-connection
problem class (no port exclusion, no firewall rules to babysit, no
discovery). The scanning/matching/invoice logic barely changes; this is
additive plumbing around a core that already works, not a rewrite of the
product.

Keep "standalone" (local Excel, no network) as an offline fallback, so a
customer can keep working if their internet drops mid-shift, syncing to
the cloud once back online. That preserves the one genuine advantage the
LAN-only architecture had.

## How it would work as a business

- **Customer**: a warehouse/reseller business signs up, creates an
  account, pays a subscription (monthly/annual).
- **What they get**: the same desktop app for as many PCs/employees as
  their plan allows, their own private cloud-hosted data (catalog,
  results, invoices — isolated from every other customer), and it works
  the moment they install it — no server setup, no LAN discovery.
- **Delivery**: "server mode" as a LAN concept disappears. Every install
  is effectively "client mode," logging into the cloud account instead of
  discovering a PC on the network.
- **Pricing shape**: recurring (matches ongoing hosting/support cost),
  likely priced per seat/device or per location. A free tier or trial
  lowers the barrier to try it.
- **Onboarding**: sign up on a website, get an account, download the
  app, log in, upload catalog, start scanning — much simpler than today's
  "set up a server on one PC, discover it from others."

## What actually has to get built

None of these are individually hard — they're standard, well-documented
problems with mature tools. The difficulty is breadth: this touches every
layer of the app, and it's a shift from "ship an app" to "run a live
service" with real uptime/security obligations.

| Piece | Effort (rough, one focused dev) | Notes |
|---|---|---|
| Multi-tenant backend + auth | 3–4 weeks | Biggest chunk. `server.py` currently has **zero auth on any endpoint** and wide-open CORS — every existing route needs an auth check + tenant scoping added before this can be internet-facing. |
| Hosting/deployment | 3–5 days | `Database` already takes a `db_path` parameter, so "one SQLite file per tenant" is a low-risk fit — no need to migrate to Postgres for a v1. Use a managed platform (Render/Railway/Fly.io) to avoid owning raw ops. |
| Billing (Stripe subscriptions + webhook) | ~1 week | Well-trodden path. |
| Desktop app changes | 1–2 weeks | `api_client.py` is already a clean REST abstraction — mostly plumbing (login screen, point at a fixed cloud URL, retire the LAN discovery UI), not a rewrite. |
| Security hardening + real beta with a paying customer | 2+ weeks, ongoing | Input validation, rate limiting, HTTPS everywhere — non-negotiable once this is public-internet-facing. |

**Total: roughly 2–3 months of focused work for a solid v1.** Not a
weekend project, not a multi-year platform rebuild — no novel engineering,
just standard SaaS scaffolding around a core that already works.

## Yearly cost to keep it running, even with zero customers

The financial downside here is small — much smaller than a typical first
business (no inventory, no lease, no equipment). Checked against current
(2026) pricing, not assumed from memory:

| Setup | Cost/year | Trade-off |
|---|---|---|
| Cheapest — free hosting tier + domain | **~$12/year** | Render's free tier works fine, but the server "sleeps" after 15 min idle and has a slow cold-start on the next request. Fine while testing/building, not great once real customers depend on it. |
| Realistic "always-on, no cold starts" — managed platform | **~$70–95/year** | Render Starter (~$7/mo) or Railway Hobby (~$5/mo) + domain (~$12–15/yr). Fully managed, HTTPS included, no server admin needed. |
| Cheapest always-on, DIY — a small VPS | **~$55–70/year** | Hetzner's cheapest instance is about €4/month + domain. Cheapest option, but you own setup/maintenance (updates, security, backups) yourself. |

On top of that:
- **Stripe (payments)**: $0 fixed cost, ever — it only takes a cut *per
  actual sale*. Zero sales means zero cost.
- **Database**: $0 extra — one SQLite file per tenant means no separate
  paid database service for v1 (see the hosting row above).
- **Email for signup/password reset**: free tiers of services like
  Resend/SendGrid comfortably cover very low volume.

**Bottom line: roughly $12–$95/year** depending on how "production-ready"
vs. "just testing" it needs to look, before a single customer pays
anything. The bigger cost is time (~2–3 months, per the effort table
above), not money — this is a low-stakes way to find out if the idea has
legs.

Sources checked 2026-07-20: [Cheapest VPS Hosting 2026 (Liquid Web)](https://www.liquidweb.com/blog/cheapest-vps-hosting/),
[Cloud VPS Cost Comparison 2026](https://apicalculators.com/blog/cloud-vps-cost-comparison-2026),
[Railway vs Render 2026 Pricing](https://thesoftwarescout.com/railway-vs-render-2026-best-platform-for-deploying-apps/),
[Render vs Railway (Render's own comparison)](https://render.com/articles/render-vs-railway).
Verify current pricing before committing — these change.

## Access gating

As of 2026-08-27, `app_desktop.py` requires a logged-in account to launch
at all — no account, no app (see `desktop/cloud-auth`). This is
**login-gated, not payment-gated**: there is no billing/subscription
system yet (see the "Billing" row above — still not started), so today
this only stops someone who never signed up, not someone who signed up
but doesn't pay. Wiring in Stripe and checking subscription status at the
same gate point is the natural next step once billing exists — it slots
into the same check (`app_desktop.py`'s startup token check), it just
needs something real to check besides "does a token exist."

## Auth hardening backlog

The backend brought over from `web-app/installable-core` (now living in
`server/` on `desktop/cloud-auth`) started as a deliberately minimal v1.
Most of the hardening items originally tracked here are done as of
2026-08-27:

- **Refresh tokens — done.** Access tokens are now 30 minutes, refresh
  tokens 30 days, individually revocable via a `sessions` table
  (`accounts.db`) checked on every refresh. `POST /api/auth/refresh`
  rotates (old refresh token revoked, new pair issued);
  `POST /api/auth/logout` revokes the current session.
  `api_client.APIClient` refreshes silently on a 401 — a dead access
  token no longer interrupts the user at all.
- **Token storage on the desktop — done.** The refresh token lives in
  the OS credential store (Keychain/Credential Manager, via `keyring`),
  not in plaintext `settings.json` — see `settings_manager.py`'s
  `get_auth_token`/`save_auth`/`clear_auth`. The access token is never
  persisted at all, kept in memory only.
- **Password hashing — done.** `server/accounts.py` hashes with
  argon2id (`argon2-cffi`), not werkzeug's pbkdf2/scrypt defaults.
- **Password reset — done.** Code-based (not link-based — this is a
  desktop app, no page for a "click this link" email to open), via
  Resend (`server/email_sender.py`). A reset revokes every existing
  session for that user.

Still open:

- **Multi-user tenants.** `accounts.db` has `tenants` + `users` but no
  `memberships`/roles table — today signup makes exactly one
  user-owns-one-tenant pair. Deliberately deferred (2026-08-27): no
  "invite a coworker" feature exists yet to use it — build the table
  alongside whenever that becomes a real feature, not before.
- **Treat the desktop client as untrusted.** Once there's more than one
  role per tenant, permissions currently expressed by hiding a PyQt
  button (if any ever are) must also be enforced server-side — assume the
  API is called directly, not just through the app.

## Open questions (not yet decided)

- Pricing model specifics (per-seat vs per-location vs flat tiers).
- How much offline fallback matters for target customers (some may have
  unreliable internet — worth understanding before assuming pure-cloud
  is acceptable for everyone).
- Whether to keep LAN server-mode available at all (e.g. as a
  self-hosted/on-prem option for customers who want it) or retire it
  entirely once cloud mode exists.
- Single shared multi-tenant backend vs. one backend instance per
  customer (simpler isolation, more ops overhead).

## Related

See also the separately-tracked standalone-mode-removal cleanup — that
refactor (collapsing standalone/server into one always-on local mode) is
orthogonal to this and was already planned as a "last task" independent
of whether the SaaS pivot happens.
