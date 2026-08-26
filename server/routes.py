# -*- coding: utf-8 -*-
"""
Genuinely new, web-only routes (Phase 2): wrap desktop-only business logic
as HTTP endpoints. No business logic lives here — this mirrors the
temp-file adapter pattern the desktop app already uses in server mode
(main_window.py's _on_generate_invoice_requested/_on_check_completeness_requested):
DB rows -> temp results.xlsx, uploaded catalog bytes -> temp catalog.xlsx,
call the existing gearledger function, clean up.
"""
import datetime
import os
import tempfile
from io import BytesIO

import flask
from flask import jsonify, request, send_file
from flask_limiter import Limiter

from gearledger.data_layer import check_catalog_completeness
from gearledger.excel_utils import get_catalog_stock
from gearledger.invoice_generator import generate_invoice_from_results
from gearledger.pipeline import process_image
from gearledger.result_ledger import _norm, rows_to_dataframe

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _write_temp_results_xlsx(rows) -> str:
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    rows_to_dataframe(rows).to_excel(path, index=False)
    return path


def _write_temp_catalog_xlsx(catalog_bytes: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    with os.fdopen(fd, "wb") as f:
        f.write(catalog_bytes)
    return path


def _cleanup(*paths: str) -> None:
    for path in paths:
        if path and os.path.exists(path):
            os.remove(path)


def init_routes(app: flask.Flask, server, limiter: Limiter) -> None:
    @app.route("/api/invoice", methods=["POST"])
    def generate_invoice():
        db = server._get_db()
        rows = db.get_all_results()
        if not rows:
            return jsonify({"ok": False, "error": "no results to invoice"}), 400

        catalog_bytes = server.get_uploaded_catalog_data()
        if not catalog_bytes:
            return jsonify({"ok": False, "error": "no catalog uploaded"}), 400

        body = request.get_json(silent=True) or {}
        try:
            weight_price = float(body.get("weight_price", 0.0))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "weight_price must be a number"}), 400

        results_path = _write_temp_results_xlsx(rows)
        catalog_path = _write_temp_catalog_xlsx(catalog_bytes)
        output_fd, output_path = tempfile.mkstemp(suffix=".xlsx")
        os.close(output_fd)
        try:
            result = generate_invoice_from_results(
                results_path, catalog_path, output_path, weight_price
            )
            if not result.get("ok"):
                return jsonify({"ok": False, "error": result.get("error")}), 400

            # Read into memory before cleanup — send_file(path) would stream
            # lazily after this handler returns, racing the os.remove below.
            with open(output_path, "rb") as f:
                invoice_bytes = f.read()
        finally:
            _cleanup(results_path, catalog_path, output_path)

        filename = f"invoice_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            BytesIO(invoice_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype=_XLSX_MIME,
        )

    @app.route("/api/completeness", methods=["GET"])
    def get_completeness():
        catalog_bytes = server.get_uploaded_catalog_data()
        if not catalog_bytes:
            return jsonify({"ok": False, "error": "no catalog uploaded"}), 400

        db = server._get_db()
        rows = db.get_all_results()

        catalog_path = _write_temp_catalog_xlsx(catalog_bytes)
        results_path = _write_temp_results_xlsx(rows) if rows else None
        try:
            result = check_catalog_completeness(catalog_path, results_path)
        finally:
            _cleanup(catalog_path, results_path)

        status = 200 if result.get("ok") else 400
        return jsonify(result), status

    @app.route("/api/catalog/stock", methods=["GET"])
    def get_catalog_stock_for_entry():
        """
        Stock preview for the manual-entry screen, mirroring the desktop's
        pre-add check (main_window.py:_show_add_dialog_and_record): how much
        of `artikul` is left for `client` after subtracting what's already
        been recorded, so the browser can show the same stock badge/clamp
        and out-of-stock block the desktop dialog does.

        Deliberately does NOT reuse gearledger.data_layer.get_results_quantity
        here — that function ignores its results_path argument and falls
        back to global network-mode state, which has no meaning in this
        per-tenant server. Already-recorded quantity is summed directly from
        this tenant's DB rows instead, using the same _norm() matching.
        """
        artikul = (request.args.get("artikul") or "").strip()
        client = (request.args.get("client") or "").strip()
        if not artikul or not client:
            return jsonify({"ok": False, "error": "artikul and client are required"}), 400

        catalog_bytes = server.get_uploaded_catalog_data()
        if not catalog_bytes:
            return jsonify({"ok": False, "error": "no catalog uploaded"}), 400

        catalog_path = _write_temp_catalog_xlsx(catalog_bytes)
        try:
            stock_result = get_catalog_stock(catalog_path, artikul, client)
        finally:
            _cleanup(catalog_path)

        if stock_result is None:
            return jsonify(
                {"ok": True, "tracked": False, "stock": None, "breakdown": None, "already_added": 0, "remaining": None}
            )

        catalog_stock_total, breakdown = stock_result

        db = server._get_db()
        target_key = _norm(artikul)
        client_key = client.upper()
        already_added = 0
        for row in db.get_all_results():
            if str(row.get("client", "")).strip().upper() != client_key:
                continue
            if _norm(row.get("artikul", "")) == target_key:
                already_added += int(row.get("quantity", 0) or 0)

        return jsonify(
            {
                "ok": True,
                "tracked": True,
                "stock": catalog_stock_total,
                "breakdown": breakdown,
                "already_added": already_added,
                "remaining": catalog_stock_total - already_added,
            }
        )

    @app.route("/api/scan", methods=["POST"])
    @limiter.limit("20 per minute")
    def scan_image():
        # Tighter than the other routes here on purpose: this is the one
        # endpoint that costs real, metered OpenAI Vision API money per
        # call, not just server compute — MAX_CONTENT_LENGTH (app.py) caps
        # payload size, this caps call frequency per IP.
        if "image" not in request.files:
            return jsonify({"ok": False, "error": "no image provided"}), 400
        image_file = request.files["image"]
        if image_file.filename == "":
            return jsonify({"ok": False, "error": "no image selected"}), 400

        catalog_bytes = server.get_uploaded_catalog_data()
        if not catalog_bytes:
            return jsonify({"ok": False, "error": "no catalog uploaded"}), 400

        suffix = os.path.splitext(image_file.filename)[1] or ".jpg"
        image_fd, image_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(image_fd, "wb") as f:
            image_file.save(f)
        catalog_path = _write_temp_catalog_xlsx(catalog_bytes)
        try:
            result = process_image(image_path, catalog_path)
            status = 200 if result.get("ok") else 400
        except Exception as exc:
            # process_image only catches some of its own failure modes
            # internally (e.g. a bad GPT JSON response) — a raised
            # exception (rate limit, network error, bad key) is the vision
            # API itself failing, not a bad request, so it's not the
            # client's fault the way the other 400s above are.
            result = {"ok": False, "error": str(exc)}
            status = 502
        finally:
            _cleanup(image_path, catalog_path)

        return jsonify(result), status
