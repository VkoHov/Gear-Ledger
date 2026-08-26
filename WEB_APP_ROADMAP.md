# Gear Ledger — Web App Feasibility & Roadmap

Status: **Exploratory — not started.** This document captures a planning
discussion, not a committed plan. Nothing here should be implemented
without an explicit go-ahead.

## How this relates to SAAS_ROADMAP.md

[`SAAS_ROADMAP.md`](./SAAS_ROADMAP.md) covers moving the **server** off the
customer's LAN and into the cloud, while the **desktop app stays** — users
still install Gear Ledger, it just points at a URL instead of discovering a
LAN peer. That doc's "multi-tenant backend + auth" work is the single
biggest piece either way, and this document assumes it as a prerequisite
rather than re-costing it.

This document answers a different, bigger question: replacing the **client**
itself — the PyQt desktop app — with a browser page, so nothing gets
installed at all. That work is *additive* on top of the SaaS roadmap, not a
substitute for it.

## Feature-by-feature web feasibility

| Feature | Today | Web path | Portability |
|---|---|---|---|
| Camera capture | OpenCV (`cv2.VideoCapture`) polling a local device | `getUserMedia`/`ImageCapture` | Straightforward |
| Vision match — OpenAI backend | Image → OpenAI vision API call | Same call, made from the server (API key can't live in browser JS) | Easy — barely changes |
| Vision match — local OCR backend | PaddleOCR (heavy native ML runtime) + heuristics, then still asks GPT to rank | Runs server-side only (or a cloud OCR API); no browser equivalent | Moves server-side, or drop it (see note below) |
| Catalog upload/matching | pandas/openpyxl, in-memory lookup cache | File upload + server-side parse, or SheetJS client-side | Straightforward |
| "Fuzzy" match pass | Actually exact string match after normalization — `fuzzywuzzy` is declared in requirements but never imported | Trivial string logic | Straightforward (and worth renaming honestly while touching it) |
| Manual part-code entry | Qt text field + background lookup | Plain form + async fetch | Straightforward |
| Add-to-results modal | PyQt dialog with quantity/stock bounds | Web modal | Straightforward |
| Results table | `pandas.DataFrame` in a `QAbstractTableModel` | Server-side query + a web data-grid component | Straightforward |
| Reset / Versions / Restore | Local filesystem archive folder, native "open in Excel" | Needs a real versioning API (mostly exists via `database.py`, not exposed over HTTP yet); "open in Excel" becomes download-only | Needs new backend routes |
| Generate Invoice | `openpyxl` workbook built locally, native save dialog | Same generation, server-side; browser file download instead of save dialog | Needs a new backend route (none exists today) |
| Check catalog completeness | Local pandas comparison | Server-side computation, same logic | Needs a new backend route |
| Import/Download results | pandas I/O + native dialogs | Upload/download endpoints | Straightforward |
| **Scale integration** | `pyserial`, direct COM/tty access | **No clean browser equivalent.** Web Serial API (Chrome/Edge only, HTTPS, per-device permission) or a thin local bridge agent forwarding serial→WebSocket | Real constraint — see Open Questions |
| Multi-language UI | Dict-based `tr()` lookup | Any JS i18n approach | Trivial |
| **Speech/TTS** | OS-native (`say`/`pyttsx3`) and Piper are both local binaries; OpenAI TTS is already cloud-based | Browser `SpeechSynthesis` API (free, quality varies by OS/browser) or server-side TTS streamed down (better control, adds cost/latency) | OS/Piper paths don't port; OpenAI path already does |
| Settings | Local JSON + native pickers | Web form backed by user profile; camera device picker still works via `getUserMedia` enumeration, serial port picker doesn't apply in Web Serial/bridge model | Mostly straightforward |
| Network mode / LAN discovery (Flask server, SSE, UDP broadcast, `api_client.py`) | Whole LAN client/server subsystem | **Disappears entirely** in a pure web model — replaced by normal login + fixed URL, same as the SaaS roadmap's cloud pivot | Net simplification, not a cost |

## Architecture

- **Backend**: extend the existing Flask API (`server.py` already has most
  results/catalog CRUD + SSE) rather than starting over. New routes needed
  for the things that are desktop-only today: invoice generation, version
  list/restore, catalog-completeness check, and the image→match pipeline
  itself (wrapping `pipeline.process_image`). Auth + multi-tenancy from the
  SaaS roadmap is a hard prerequisite here, not optional — a public web page
  can't work against an unauthenticated API.
- **Frontend**: a genuine new SPA (React or similar) — this is the one
  piece with no existing code to build on, since it replaces
  `main_window.py`'s entire UI.
- **Scale**: pick one — Web Serial API (zero install, Chrome/Edge only) or a
  small local bridge agent (thin cross-platform service forwarding
  serial→WebSocket, works in any browser). See Open Questions.
- **Camera**: `getUserMedia`, no real risk here.
- **TTS**: recommend browser `SpeechSynthesis` first (free, zero latency
  added); fall back to server-side only if voice quality/consistency turns
  out to matter enough to justify the cost.
- **Vision**: the OpenAI backend barely changes shape (it's already a
  network call). The local PaddleOCR backend is the one piece worth
  questioning — it's a heavy native runtime that only makes sense
  self-hosted, and the research pass turned up signs it may already be a
  half-used fallback path (fuzzy-match libraries declared but unused
  suggest some scope drift already). Worth deciding whether it's pulling
  its weight before porting it.

## Effort estimate

Builds **on top of** the SaaS roadmap's table (not a replacement for it):

| Piece | Effort | Notes |
|---|---|---|
| Multi-tenant backend + auth | 3–4 weeks | Same item as the SaaS roadmap — now mandatory, not optional |
| New backend routes (invoice, versions, completeness, image→match) | 1–2 weeks | Mostly wrapping existing desktop-side logic as HTTP routes |
| Frontend web app (camera, review/confirm, manual entry, results grid, settings, invoice download, versions UI, i18n) | 4–8 weeks | The big net-new item — a real UI rewrite, not plumbing |
| Scale connectivity | 3–5 days (Web Serial only) or 1–2 weeks (local bridge agent) | Depends on the browser-support decision below |
| TTS | 2–5 days (browser API) or more (server-side voice) | |
| Hosting/deployment | 3–5 days | Same as SaaS roadmap |
| Billing (if monetizing) | ~1 week | Same as SaaS roadmap |
| Security hardening + beta | 2+ weeks, ongoing | Same as SaaS roadmap |

**Total: roughly 4–5.5 months of focused work** for full feature parity as
a real web app (the SaaS roadmap's 2–3 months, plus another 6–10 weeks for
the frontend rewrite and hardware bridge). Not a rewrite of the business
logic — the matching/pricing/invoicing core stays — but the UI layer is a
genuine from-scratch project.

## Open questions

- **Is full web replacement actually the goal**, or is the underlying ask
  "stop making people install/configure a LAN server"? The SaaS roadmap
  alone (desktop app + cloud backend) already solves that specific pain for
  a fraction of the cost — see Recommendation below.
- **Scale: Web Serial vs. local bridge.** Web Serial is free (browser API,
  no install) but Chrome/Edge only, HTTPS-only, one-time permission per
  device. A bridge agent works in any browser but means every scanning
  workstation still needs something installed locally — you don't fully
  escape "install something," just shrink it.
- **Is PaddleOCR worth porting?** It's a heavy, self-hosted-only dependency;
  worth confirming it's actually adding matching accuracy over the OpenAI
  path before committing to running it on a server.
- **Is voice feedback essential** (hands-free warehouse workflow) or
  nice-to-have? Determines whether server-side TTS is worth its cost/latency
  over free browser `SpeechSynthesis`.
- **Offline tolerance.** Standalone mode today gives zero-setup offline use.
  A pure web app has none of that unless you build a PWA + service worker +
  local cache — a separate project on top of everything above.
- **Is mobile/tablet access actually wanted?** This is the strongest reason
  to go full web rather than just cloud-backing the desktop app — camera
  capture works fine on a phone, and it's the one thing the desktop app
  fundamentally can't offer.

## Recommendation

The colleague's actual question — "why isn't this a web app, can the scale
connect" — is likely pointing at install/setup friction, which the SaaS
roadmap already solves on its own: same desktop app, but it points at a
cloud URL instead of a LAN server, no port/firewall babysitting. Going full
web is justified specifically if **zero-install, any-device access**
(especially phones/tablets, or letting non-scanning staff use it without
installing anything) is a real goal — not just as a way to avoid the LAN
setup pain, which is cheaper to fix directly.

**A middle path worth considering**: keep the desktop app for the
scanning workstations (camera + scale + TTS stay exactly as they are,
unaffected by any of this), backed by the same cloud multi-tenant API from
the SaaS roadmap — and separately build a **lightweight web dashboard**
(view results, generate/download invoices, browse catalog, check
completeness) for anyone who doesn't need to scan. That reuses the existing
API surface almost entirely, skips camera/scale/TTS complexity altogether,
and is roughly 2–3 weeks of frontend work instead of 6–10 — most of the
"why can't I just check this from my browser" value at a fraction of the
cost.

## Related

See [`SAAS_ROADMAP.md`](./SAAS_ROADMAP.md) for the cloud-hosting/auth/billing
plan this document builds on, and the separately-tracked
standalone-mode-removal cleanup (already implemented — see git history),
which is unrelated to either roadmap.
