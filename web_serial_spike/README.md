# Web Serial scale spike

This is the Phase 0.5 spike from `FULL_WEB_APP_PLAN.md` — a throwaway test
page, **not part of the app**, that answers one question: can the scale be
read directly from a browser at all, with the same parsing/stability
behavior the desktop app relies on?

It deliberately re-implements the exact logic from
`gearledger/desktop/scale.py` and `scale_widget.py` (the weight regex, the
zero-value suppression, the stability/threshold/settle-time check) in
JavaScript — the goal is to test whether *that specific algorithm* behaves
the same when fed by Web Serial instead of `pyserial`, not to write a
better algorithm.

## How to run it

Web Serial requires a "secure context" — it won't work opening the file
directly via `file://` in most browsers. Serve it locally instead:

```bash
cd web_serial_spike
python3 -m http.server 8000
```

Then open **Chrome or Edge** (Web Serial isn't supported in Safari/Firefox)
at `http://localhost:8000`.

1. Plug in the scale via USB-serial, same as you would for the desktop app.
2. Click **Connect to scale** — a native browser dialog lists available
   serial ports; pick the scale's port. (First connect needs this manual
   picker; the permission is remembered per-site after that.)
3. Put a known weight on the scale and watch the page. Check for:
   - Readings appear at all (confirms the browser can read the port).
   - The raw log (`raw: ...`) matches what you'd see in the desktop app's
     terminal output (`Scale raw: ...` in `scale.py`).
   - The displayed weight settles to **"✓ STABLE"** after ~2 seconds of a
     steady weight, same as the desktop app's stability behavior.
   - Removing the weight and watching it return to zero doesn't cause
     flickering between 0 and the old value (the zero-suppression logic).
4. Unplug the scale mid-read and confirm the page notices ("Connection
   lost" / "Device disconnected") instead of hanging silently.

## What a pass/fail here actually means

- **Works well** → Web Serial is confirmed as the right call; Phase 4 in
  `FULL_WEB_APP_PLAN.md` proceeds to harden this into production code.
- **Flaky, wrong baud behavior, or the scale needs a write/command this
  page never sends** → fall back to the bridge-agent approach noted in
  Phase 4 — a small local service forwarding serial→WebSocket. Not a dead
  end, just a different (still known-working) path.

Try the other baud rates in the dropdown if the log shows garbage instead
of readable text — that's almost always a baud mismatch, not a fundamental
Web Serial problem.
