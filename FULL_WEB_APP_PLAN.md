# Gear Ledger — Full Web App Migration Plan

Status: **Exploratory — not started.** This is a plan for discussion, not a
committed roadmap. Nothing here should be implemented without an explicit
go-ahead, and it should be re-confirmed before starting given the size of
the commitment (see `WEB_APP_ROADMAP.md`'s 4–5.5 month estimate).

This plan is for the **full replacement** path — the PyQt desktop app goes
away entirely, replaced by a browser SPA. If the actual goal turns out to
be "let office staff check things without installing anything," the
[`DASHBOARD_SPEC.md`](./DASHBOARD_SPEC.md) middle path gets ~80% of that
value for a fraction of the cost — worth re-confirming this is really the
wanted outcome (mobile/tablet access, zero-install for scanning staff too)
before committing to the steps below.

## Repo structure: split, don't rewrite in place

**Recommendation: keep the backend in this repo (`Gear-Ledger`), create a
new repo for the frontend (e.g. `gear-ledger-web`).**

Why not one monorepo:
- This repo already carries a lot of desktop-specific baggage unrelated to
  a web app — `build_exe.py`, `build_nuitka.py`, `ICON_GUIDE.md`,
  `BUILD_INSTRUCTIONS.md`, PyInstaller/Nuitka packaging. A frontend
  contributor (or future you, six months from now) shouldn't have to wade
  through desktop packaging tooling to find `App.tsx`.
- The frontend is a genuinely new codebase with its own toolchain
  (Node/npm, a bundler, its own lint/test/CI setup) that shares zero
  history with the Python code. Mixing `node_modules` and a Python venv in
  one repo is doable but buys nothing here.

Why not two repos for backend+frontend both:
- The backend isn't new code — it's `gearledger/server.py` and friends,
  extended in place. Moving it would be pure busywork with no benefit, and
  it's the same backend the SaaS roadmap's cloud pivot needs regardless of
  whether the frontend rewrite happens. Splitting it out would just add
  cross-repo coordination for zero gain.
- Backend changes (new routes) and their consumption (frontend calling
  them) will happen together constantly during this build — keeping the
  backend where its business logic already lives (`data_layer.py`,
  `invoice_generator.py`, `database.py`) means you're not synchronizing
  two release cadences for code that changes in lockstep with itself.

So: **one new repo, frontend only.** Backend work is a phase inside
*this* repo.

## Suggested frontend stack

No existing precedent to match, so picking a boring, well-supported
default rather than optimizing: **React + TypeScript + Vite**, a data
grid for the results table (e.g. TanStack Table), TanStack Query for
API calls/caching, and plain CSS or Tailwind for styling. Nothing here is
load-bearing — swap freely if you have a preference — but it's worth
deciding once at the start of Phase 3 rather than mid-build.

## Phased plan

### Phase 0 — Decisions (before writing any code)
- [ ] Confirm full replacement is really the goal (see the note above).
- [ ] Create the new frontend repo, pick the stack.
- [ ] Pick a hosting target for the backend (Render/Railway/Fly.io, per
      `SAAS_ROADMAP.md`) and one for the frontend (Vercel/Netlify/Cloudflare
      Pages are the standard fit for a Vite SPA).

#### Tooling decisions

| Concern | Choice | Why |
|---|---|---|
| **Auth** | Self-rolled JWT — `Flask-JWT-Extended` for tokens + `werkzeug.security` (already a Flask dependency) for password hashing. One central `accounts`/`tenants` table (separate from the per-tenant results DBs) mapping login → tenant ID → that tenant's `db_path`. | Matches the cost-conscious framing already in `SAAS_ROADMAP.md`; auth requirements here are simple (email/password, one tenant per account, no SSO); JWT fits a separate-origin SPA calling a JSON API without session-cookie/CORS headaches. Alternative worth naming: **Supabase Auth** (free tier) if you'd rather not own password-reset emails and security patching yourself — costs a dependency on their service, buys you not maintaining that path. |
| **Backend hosting** | Render or Railway, per `SAAS_ROADMAP.md`'s existing cost table (~$70–95/year, always-on). | Already evaluated there; near-zero config for a Flask app. Free tiers sleep after 15 min idle — fine while testing, not once a real customer depends on it. |
| **Production WSGI server** | `gunicorn` in front of the Flask app. | `server.py:614` currently calls `werkzeug.serving.make_server(..., threaded=True)` directly — fine for a LAN server on one machine, not meant for public-internet concurrent load. Swapping to `gunicorn server:app` is a config change, not a rewrite. |
| **CORS** | Lock `CORS(self.app)` (`server.py:48`, currently wide open) down to `origins=["https://<frontend-domain>"]`. | Needed the moment there's a real frontend origin to allow instead of the LAN's "anyone on the network" assumption. |
| **Frontend hosting** | Vercel, Netlify, or Cloudflare Pages. | Free at this traffic level, zero-config for a Vite build — not a decision that needs much deliberation. |

### Phase 0.5 — De-risk the scale **before** committing to Phases 1–3

This phase exists specifically because the biggest fear here isn't a
coding risk, it's a **sunk-cost risk**: spending months on auth +
multi-tenancy + a full frontend rewrite, only to find out afterward that
Web Serial doesn't actually work well against the real hardware. That's
solved by moving the cheapest, most decisive test to the very front of
the plan, before any of the expensive phases start.

- [ ] Build the bare HTML/JS Web Serial spike (no framework, no auth, no
      backend — just a page that requests the port and prints readings).
- [ ] Test it against the **actual scale hardware** you use today, side by
      side with the desktop app's readings, including the edge cases
      `scale.py:86-91` already handles deliberately (zero-value readings,
      last-stable-value fallback) — confirm the raw serial data behaves the
      same from a browser as it does from `pyserial`.
- [ ] Only proceed to Phase 1 once this is confirmed working. If it
      *doesn't* work well (flaky reads, a scale that needs a write/command
      handshake this one doesn't, an OS/driver quirk), the fallback is the
      **bridge agent** noted in Phase 4 — costs a small local install per
      workstation, but is a known-working escape hatch, not a dead end.

This turns "what if the scale doesn't work after we've built everything
else" into "we know within days whether the scale works, before spending
a single hour on auth or the frontend."

### Phase 1 — Auth + multi-tenancy (3–4 weeks)
This is the SaaS roadmap's core item, and it's a hard prerequisite for
*every* later phase — a public web page can't work against today's
unauthenticated `server.py`.
- [ ] Add login/signup routes and session/token handling to `server.py`.
- [ ] Add an auth-check + tenant-scoping wrapper around every existing
      route (`/api/results`, `/api/catalog`, etc. currently have none).
- [ ] Move from "one shared SQLite file" to "one SQLite file per tenant"
      (`Database` already takes a `db_path` param — this is config, not a
      rewrite).
- [ ] Desktop app gets a login screen pointing at the cloud URL (needed
      either way per the SaaS roadmap, do this once).

### Phase 2 — Backend made web-complete (1–2 weeks)
Wrap existing desktop-only logic as HTTP routes; no new business logic.
- [ ] `POST /api/invoice` — wraps `invoice_generator.generate_invoice_from_results`
      via the temp-file adapter pattern already used in
      `main_window.py:2857` (DB rows → temp xlsx, in-memory catalog bytes →
      temp xlsx, call existing function, stream result, clean up).
- [ ] `GET /api/completeness` — wraps `data_layer.check_catalog_completeness`
      the same way.
- [ ] `POST /api/scan` (new) — wraps `pipeline.process_image` so the
      browser can POST a captured frame and get a match back. This is new
      surface area the dashboard never needed — the core scanning loop has
      to become a request/response API call for the first time.
- [ ] **Fix catalog persistence.** `self._catalog_data` today is in-memory
      only (`server.py`) — fine for a LAN server that rarely restarts, not
      fine once this is the only path in and a deploy wipes it. Persist
      catalog bytes per-tenant (DB blob or object storage) as part of this
      phase, not after — full replacement has no desktop fallback to
      re-upload from.
- [ ] CORS config for the new frontend's origin.

### Phase 3 — Frontend: core screens (4–8 weeks, the big item)
Rebuilds `main_window.py`'s UI from scratch — no shortcuts here, this is
where most of the calendar time goes.
- [ ] App shell: routing, auth/login flow, layout.
- [ ] Camera capture screen (`getUserMedia`) + review/confirm modal
      (mirrors the desktop "add to results" dialog).
- [ ] Manual part-code entry (plain form + async fetch against
      `/api/scan` or a direct lookup route).
- [ ] Results grid (reuse the dashboard spec's Results page design if
      `DASHBOARD_SPEC.md` was already built — real overlap here).
- [ ] Catalog upload/browse, completeness report, invoice generation —
      same overlap with the dashboard spec.
- [ ] Settings page (camera device picker via `getUserMedia` enumeration;
      no serial port picker needed yet — see Phase 4).
- [ ] i18n (port the existing dict-based `tr()` lookups to a JS i18n lib).

### Phase 4 — Scale connectivity, production version (3–5 days Web Serial, or 1–2 weeks bridge agent)
The go/no-go spike already happened in Phase 0.5, before Phases 1–3 were
built — this phase is just hardening that already-proven approach, not
re-deciding whether it works. Recommendation is Web Serial, since the
scale protocol is plain ASCII text and read-only (`scale.py:6-19`, no
writes — `tare` is a software-side offset only).
- [ ] Production version: line-buffering over raw chunks (Web Serial has
      no `readline()`), reconnect/error handling matching
      `scale_widget.py:715`'s connection-lost behavior, port-permission UX
      (`navigator.serial.getPorts()` for silent reconnect).
- [ ] Wire into the scanning screen from Phase 3.

### Phase 5 — TTS (2–5 days)
- [ ] Browser `SpeechSynthesis` API first — free, zero added latency.
- [ ] Only build server-side TTS streaming if voice quality/consistency
      turns out to matter enough in real use to justify the cost — don't
      build it speculatively.

### Phase 6 — PaddleOCR decision (0 days if dropped, else re-costed separately)
- [ ] Before porting anything: confirm PaddleOCR is actually adding match
      accuracy over the OpenAI vision path in practice. If it's a
      half-used fallback (the `fuzzywuzzy`-declared-but-unused pattern
      elsewhere in the codebase suggests some scope drift already), drop
      it and simplify — one less heavy native dependency to run
      server-side.

### Phase 7 — Offline/PWA tolerance (open-ended, scope explicitly before starting)
- [ ] Decide whether this is actually required (per `WEB_APP_ROADMAP.md`'s
      open question) — there's no existing analog anywhere in the
      codebase to build from, unlike every other phase here.
- [ ] If yes: service worker + local cache + background sync, treated as
      its own project with its own estimate, not folded into Phase 3's.

### Phase 8 — Hosting, security hardening, beta (2+ weeks, ongoing)
Same item as the SaaS roadmap — input validation, rate limiting, HTTPS
everywhere, non-negotiable once public-internet-facing.
- [ ] Deploy backend + frontend to their chosen hosts.
- [ ] Real beta with a paying/pilot customer before wider rollout.

### Phase 9 — Cutover decision
- [ ] Decide whether the desktop app is retired outright once the web app
      reaches parity, or kept running in parallel indefinitely (e.g. for
      scanning-heavy users who prefer it, or as an offline fallback if
      Phase 7 is skipped). This has real long-term support-burden
      implications either way — worth deciding deliberately, not by
      default.

## Sequencing notes

- **Phase 0.5 (scale spike) comes before Phase 1, deliberately out of
  numeric order.** It's the cheapest possible test of the single
  scariest unknown — everything else in this plan is well-trodden web
  engineering with a clear existing analog to build from; the scale is
  the one piece that depends on real, specific hardware behaving the way
  the desktop app's `pyserial` code assumes. Confirming that early means
  months of auth/frontend work never get built on top of an assumption
  that turns out to be wrong.
- Phases 1–2 are strict prerequisites for everything after — no frontend
  work can be usefully tested against a real backend until auth exists.
- Phases 4–6 (scale hardening, TTS, PaddleOCR) don't depend on each other
  and can be reordered or parallelized once Phase 3's core shell exists.
- Phase 7 is the one phase worth explicitly scoping or explicitly
  deferring — it's the only piece without a clear existing analog to
  estimate from.

## Related

See [`WEB_APP_ROADMAP.md`](./WEB_APP_ROADMAP.md) for the feasibility
analysis and effort table this plan sequences, [`SAAS_ROADMAP.md`](./SAAS_ROADMAP.md)
for the Phase 1 auth/multi-tenancy prerequisite in full detail, and
[`DASHBOARD_SPEC.md`](./DASHBOARD_SPEC.md) for the cheaper middle path this
plan supersedes if chosen instead.
