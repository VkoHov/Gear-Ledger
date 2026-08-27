# -*- coding: utf-8 -*-
"""
Admin: a small internal-only page for manually activating/deactivating
accounts until Stripe billing exists. Protected by the normal auth system
— a real email/password login against /api/auth/login — plus an
is_admin flag on the logging-in user's account, not a separate secret.
See accounts.py's promote_to_admin_if_listed for how someone becomes an
admin in the first place (there's no route that grants it — deliberately;
an admin tool that could create more admins through itself would be its
own privilege-escalation surface).
"""
import flask
from flask import Response, jsonify

from accounts import get_accounts_store


def _require_admin():
    """Call at the top of every /api/admin/* route. Returns an error
    Response to short-circuit with, or None to proceed.

    By the time this runs, auth.py's before_request has already verified
    the access token and set flask.g.user_id (this path isn't in
    _PUBLIC_PATHS) and has already skipped the tenant-subscription check
    (this path is under _ADMIN_PATH_PREFIX) — this is what actually
    enforces "and are you staff," fresh from the DB rather than trusting
    anything baked into the token itself.
    """
    user = get_accounts_store().get_user_by_id(flask.g.user_id)
    if user is None or not user["is_admin"]:
        return jsonify({"error": "forbidden"}), 403
    return None


def init_admin(app: flask.Flask, limiter) -> None:
    @app.route("/admin", methods=["GET"])
    def admin_page():
        return Response(_ADMIN_HTML, mimetype="text/html")

    @app.route("/api/admin/accounts", methods=["GET"])
    @limiter.limit("60 per minute")
    def admin_list_accounts():
        error = _require_admin()
        if error:
            return error
        return jsonify({"accounts": get_accounts_store().list_accounts_with_status()}), 200

    @app.route("/api/admin/accounts/<tenant_id>/activate", methods=["POST"])
    @limiter.limit("60 per minute")
    def admin_activate(tenant_id):
        error = _require_admin()
        if error:
            return error
        if not get_accounts_store().set_subscription_status(tenant_id, "active"):
            return jsonify({"error": "tenant not found"}), 404
        return jsonify({"ok": True}), 200

    @app.route("/api/admin/accounts/<tenant_id>/deactivate", methods=["POST"])
    @limiter.limit("60 per minute")
    def admin_deactivate(tenant_id):
        error = _require_admin()
        if error:
            return error
        if not get_accounts_store().set_subscription_status(tenant_id, "inactive"):
            return jsonify({"error": "tenant not found"}), 404
        return jsonify({"ok": True}), 200

    @app.route("/api/admin/accounts/<tenant_id>/generate-reset-code", methods=["POST"])
    @limiter.limit("30 per minute")
    def admin_generate_reset_code(tenant_id):
        """Manual alternative to the emailed reset code -- for a small
        number of personally-known customers, relaying a code yourself
        (phone, chat, in person) is a reasonable substitute for having
        Resend's domain verification set up. Same underlying code and
        /api/auth/password-reset/confirm endpoint as the emailed flow;
        this just skips the email step and hands the code to the admin
        instead."""
        error = _require_admin()
        if error:
            return error
        user = get_accounts_store().get_user_by_tenant_id(tenant_id)
        if user is None:
            return jsonify({"error": "tenant not found"}), 404
        code = get_accounts_store().create_password_reset(user["id"])
        return jsonify({"ok": True, "code": code, "email": user["email"]}), 200


_ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gear Ledger Admin</title>
<style>
  :root {
    --bg: #f5f7f9; --surface: #ffffff; --surface-2: #eef1f4;
    --text: #1f2c38; --text-muted: #64758a; --border: #dde3ea;
    --accent: #2f7fd1; --accent-soft: #e8f1fb;
    --success: #1f9d63; --success-soft: #e5f6ed;
    --danger: #d6455a; --danger-soft: #fbeaec;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .hidden { display: none !important; }

  .lock-screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }
  .lock-card { width: 100%; max-width: 360px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; box-shadow: 0 6px 20px rgba(31,44,56,0.06); padding: 32px 28px 28px; }
  .lock-mark { width: 40px; height: 40px; border-radius: 10px; background: var(--accent-soft); color: var(--accent);
    display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; margin-bottom: 18px; }
  .lock-card h1 { font-size: 19px; font-weight: 600; margin: 0 0 4px; }
  .lock-card p { font-size: 13.5px; color: var(--text-muted); margin: 0 0 20px; line-height: 1.5; }
  .field-label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; margin-top: 14px; }
  .field-input { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--bg); color: var(--text); font-size: 13.5px; }
  .field-input:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-color: transparent; }
  .btn { appearance: none; border: none; border-radius: 8px; padding: 10px 16px; font-size: 13.5px;
    font-weight: 600; cursor: pointer; }
  .btn:active { transform: translateY(1px); }
  .btn-primary { width: 100%; background: var(--accent); color: #fff; margin-top: 18px; }
  .btn-primary:disabled { opacity: 0.6; cursor: default; }
  .form-error { margin-top: 14px; font-size: 12.5px; color: var(--danger); min-height: 1.2em; }

  .app { min-height: 100vh; }
  .topbar { display: flex; align-items: center; justify-content: space-between; padding: 16px 28px;
    border-bottom: 1px solid var(--border); background: var(--surface); }
  .brand { display: flex; align-items: center; gap: 10px; }
  .brand-mark { width: 30px; height: 30px; border-radius: 8px; background: var(--accent-soft); color: var(--accent);
    display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }
  .brand-name { font-weight: 600; font-size: 14.5px; }
  .brand-tag { font-size: 11px; color: var(--text-muted); background: var(--surface-2); padding: 2px 8px;
    border-radius: 999px; margin-left: 4px; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; }
  .lock-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); border-radius: 7px;
    padding: 7px 12px; font-size: 12.5px; cursor: pointer; }
  .lock-btn:hover { color: var(--text); border-color: var(--text-muted); }

  main { max-width: 980px; margin: 0 auto; padding: 32px 28px 64px; }
  .page-head { margin-bottom: 24px; }
  .page-head h1 { font-size: 21px; font-weight: 650; margin: 0 0 4px; }
  .page-head p { margin: 0; color: var(--text-muted); font-size: 13.5px; }

  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 28px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; }
  .stat-label { font-size: 11.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em;
    font-weight: 600; margin-bottom: 8px; }
  .stat-value { font-family: ui-monospace, monospace; font-size: 26px; font-weight: 500; }
  .stat-value.success { color: var(--success); }
  .stat-value.muted { color: var(--text-muted); }

  .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 18px;
    border-bottom: 1px solid var(--border); }
  .panel-head h2 { font-size: 14.5px; font-weight: 600; margin: 0; }
  .search-input { width: 220px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 7px;
    background: var(--bg); color: var(--text); font-size: 13px; }

  .table-scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; min-width: 640px; }
  thead th { text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--text-muted); padding: 10px 18px; border-bottom: 1px solid var(--border); background: var(--surface-2); }
  tbody td { padding: 13px 18px; border-bottom: 1px solid var(--border); font-size: 13.5px; vertical-align: middle; }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: var(--surface-2); }
  .cell-email { font-family: ui-monospace, monospace; font-size: 13px; }
  .cell-muted { color: var(--text-muted); font-family: ui-monospace, monospace; font-size: 12.5px; }

  .pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px 3px 8px; border-radius: 999px;
    font-size: 12px; font-weight: 600; }
  .pill-dot { width: 6px; height: 6px; border-radius: 999px; }
  .pill-active { background: var(--success-soft); color: var(--success); }
  .pill-active .pill-dot { background: var(--success); }
  .pill-inactive { background: var(--surface-2); color: var(--text-muted); }
  .pill-inactive .pill-dot { background: var(--text-muted); }

  .row-actions { display: flex; justify-content: flex-end; gap: 8px; }
  .btn-toggle { border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: 7px;
    padding: 6px 12px; font-size: 12.5px; font-weight: 600; cursor: pointer; min-width: 92px; }
  .btn-toggle.is-active { color: var(--danger); border-color: var(--danger-soft); }
  .btn-toggle.is-active:hover { background: var(--danger-soft); }
  .btn-toggle.is-inactive { color: var(--success); border-color: var(--success-soft); }
  .btn-toggle.is-inactive:hover { background: var(--success-soft); }
  .btn-toggle:disabled { opacity: 0.5; cursor: default; }
  .btn-secondary { border: 1px solid var(--border); background: var(--surface); color: var(--text-muted);
    border-radius: 7px; padding: 6px 12px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
  .btn-secondary:hover { color: var(--text); border-color: var(--text-muted); }

  .empty-state { padding: 40px 18px; text-align: center; color: var(--text-muted); font-size: 13.5px; }
  .foot-note { margin-top: 18px; font-size: 12px; color: var(--text-muted); line-height: 1.6; max-width: 62ch; }

  .modal-overlay { position: fixed; inset: 0; background: rgba(15,20,25,0.45); display: flex;
    align-items: center; justify-content: center; padding: 24px; z-index: 10; }
  .modal-overlay.hidden { display: none; }
  .modal-card { width: 100%; max-width: 360px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; box-shadow: 0 8px 24px rgba(28,39,51,0.15); padding: 24px; }
  .modal-card h2 { font-size: 16px; font-weight: 600; margin: 0 0 6px; }
  .modal-card p { font-size: 13px; color: var(--text-muted); margin: 0 0 16px; line-height: 1.5; }
  .modal-code { font-family: ui-monospace, monospace; font-size: 26px; font-weight: 600; letter-spacing: 3px;
    text-align: center; background: var(--surface-2); border-radius: 8px; padding: 14px; margin-bottom: 16px; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
</head>
<body>

<div class="lock-screen" id="lockScreen">
  <div class="lock-card">
    <div class="lock-mark">GL</div>
    <h1>Admin access</h1>
    <p>Log in with your Gear Ledger account. Only accounts flagged as admin can see anything past this screen.</p>
    <form id="loginForm">
      <label class="field-label" for="emailInput">Email</label>
      <input class="field-input" id="emailInput" type="email" autocomplete="username" required>
      <label class="field-label" for="passwordInput">Password</label>
      <input class="field-input" id="passwordInput" type="password" autocomplete="current-password" required>
      <button class="btn btn-primary" id="loginBtn" type="submit">Log In</button>
      <div class="form-error" id="loginError"></div>
    </form>
  </div>
</div>

<div class="app hidden" id="app">
  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">GL</div>
      <div class="brand-name">Gear Ledger</div>
      <div class="brand-tag">Admin</div>
    </div>
    <button class="lock-btn" id="logoutBtn">Log out</button>
  </div>

  <main>
    <div class="page-head">
      <h1>Accounts</h1>
      <p>Activate or deactivate a tenant's access — a manual stand-in until Stripe billing exists.</p>
    </div>

    <div class="stats">
      <div class="stat-card"><div class="stat-label">Total accounts</div><div class="stat-value" id="statTotal">—</div></div>
      <div class="stat-card"><div class="stat-label">Active</div><div class="stat-value success" id="statActive">—</div></div>
      <div class="stat-card"><div class="stat-label">Inactive</div><div class="stat-value muted" id="statInactive">—</div></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>All accounts</h2>
        <input class="search-input" id="searchInput" type="text" placeholder="Search by email…">
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Email</th><th>Signed up</th><th>Status</th><th style="text-align:right;">Action</th></tr></thead>
          <tbody id="tableBody"></tbody>
        </table>
      </div>
    </div>
    <p class="foot-note" id="footNote"></p>
  </main>
</div>

<div class="modal-overlay hidden" id="resetCodeModal">
  <div class="modal-card">
    <h2>Password reset code</h2>
    <p id="resetCodeEmail"></p>
    <div class="modal-code" id="resetCodeValue"></div>
    <p>Relay this to the customer yourself (phone, chat, in person) — it expires in 15 minutes. They enter it in the desktop app's "Reset Password" screen.</p>
    <div class="modal-actions">
      <button class="btn-secondary" id="resetCodeCopyBtn">Copy</button>
      <button class="btn-toggle is-inactive" id="resetCodeCloseBtn">Done</button>
    </div>
  </div>
</div>

<script>
(function () {
  var accessToken = null;
  var accounts = [];

  var lockScreen = document.getElementById("lockScreen");
  var app = document.getElementById("app");
  var loginForm = document.getElementById("loginForm");
  var loginBtn = document.getElementById("loginBtn");
  var loginError = document.getElementById("loginError");
  var logoutBtn = document.getElementById("logoutBtn");
  var searchInput = document.getElementById("searchInput");
  var tableBody = document.getElementById("tableBody");

  function showApp() {
    lockScreen.classList.add("hidden");
    app.classList.remove("hidden");
  }
  function showLock(message) {
    accessToken = null;
    app.classList.add("hidden");
    lockScreen.classList.remove("hidden");
    loginError.textContent = message || "";
  }

  loginForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = document.getElementById("emailInput").value.trim();
    var password = document.getElementById("passwordInput").value;
    loginError.textContent = "";
    loginBtn.disabled = true;
    loginBtn.textContent = "Logging in…";

    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password }),
    })
      .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
      .then(function (result) {
        if (result.status !== 200) {
          throw new Error(result.data.error || ("HTTP " + result.status));
        }
        accessToken = result.data.access_token;
        document.getElementById("passwordInput").value = "";
        showApp();
        return loadAccounts();
      })
      .catch(function (err) {
        loginError.textContent = err.message || "Login failed";
      })
      .finally(function () {
        loginBtn.disabled = false;
        loginBtn.textContent = "Log In";
      });
  });

  logoutBtn.addEventListener("click", function () {
    showLock("");
  });

  function apiFetch(path, options) {
    options = options || {};
    options.headers = Object.assign({}, options.headers, { Authorization: "Bearer " + accessToken });
    return fetch(path, options).then(function (res) {
      if (res.status === 401) {
        showLock("Your session expired — please log in again.");
        throw new Error("session expired");
      }
      if (res.status === 403) {
        showLock("This account doesn't have admin access.");
        throw new Error("forbidden");
      }
      return res.json().then(function (data) { return { status: res.status, data: data }; });
    });
  }

  function loadAccounts() {
    return apiFetch("/api/admin/accounts").then(function (result) {
      accounts = result.data.accounts || [];
      render();
    });
  }

  function toggleAccount(tenantId, currentlyActive) {
    var action = currentlyActive ? "deactivate" : "activate";
    apiFetch("/api/admin/accounts/" + tenantId + "/" + action, { method: "POST" })
      .then(loadAccounts)
      .catch(function () {});
  }
  window.__toggleAccount = toggleAccount;

  var resetCodeModal = document.getElementById("resetCodeModal");
  var resetCodeEmail = document.getElementById("resetCodeEmail");
  var resetCodeValue = document.getElementById("resetCodeValue");

  function generateResetCode(tenantId) {
    // Manual alternative to the emailed reset flow -- looks up the email
    // from the already-loaded accounts list rather than passing it
    // through the onclick attribute, so there's no need to worry about
    // escaping arbitrary email text into inline JS.
    var account = accounts.filter(function (a) { return a.tenant_id === tenantId; })[0];
    apiFetch("/api/admin/accounts/" + tenantId + "/generate-reset-code", { method: "POST" })
      .then(function (result) {
        resetCodeEmail.textContent = "For " + (account ? account.email : result.data.email);
        resetCodeValue.textContent = result.data.code;
        resetCodeModal.classList.remove("hidden");
      })
      .catch(function () {});
  }
  window.__generateResetCode = generateResetCode;

  document.getElementById("resetCodeCloseBtn").addEventListener("click", function () {
    resetCodeModal.classList.add("hidden");
  });
  document.getElementById("resetCodeCopyBtn").addEventListener("click", function () {
    var btn = document.getElementById("resetCodeCopyBtn");
    navigator.clipboard.writeText(resetCodeValue.textContent).then(function () {
      btn.textContent = "Copied!";
      setTimeout(function () { btn.textContent = "Copy"; }, 1500);
    });
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function render() {
    var query = searchInput.value.trim().toLowerCase();
    var filtered = accounts.filter(function (a) { return a.email.toLowerCase().indexOf(query) !== -1; });

    if (filtered.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="4"><div class="empty-state">No accounts match.</div></td></tr>';
    } else {
      tableBody.innerHTML = filtered.map(function (a) {
        var active = a.subscription_status === "active";
        return (
          '<tr>' +
          '<td class="cell-email">' + escapeHtml(a.email) + '</td>' +
          '<td class="cell-muted">' + escapeHtml((a.created_at || "").split(" ")[0]) + '</td>' +
          '<td><span class="pill ' + (active ? "pill-active" : "pill-inactive") + '">' +
            '<span class="pill-dot"></span>' + (active ? "Active" : "Inactive") + '</span></td>' +
          '<td><div class="row-actions">' +
            '<button class="btn-toggle ' + (active ? "is-active" : "is-inactive") + '" ' +
            'onclick="window.__toggleAccount(\\'' + a.tenant_id + '\\', ' + active + ')">' +
            (active ? "Deactivate" : "Activate") + '</button>' +
          '</div></td>' +
          '</tr>'
        );
      }).join("");
    }

    document.getElementById("statTotal").textContent = accounts.length;
    document.getElementById("statActive").textContent = accounts.filter(function (a) { return a.subscription_status === "active"; }).length;
    document.getElementById("statInactive").textContent = accounts.filter(function (a) { return a.subscription_status !== "active"; }).length;
    document.getElementById("footNote").textContent =
      "Toggling status here updates the account's subscription_status directly — takes effect on its next login or API call, no deploy needed.";
  }

  searchInput.addEventListener("input", render);
})();
</script>
</body>
</html>
"""
