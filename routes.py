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

from gearledger.data_layer import check_catalog_completeness
from gearledger.invoice_generator import generate_invoice_from_results
from gearledger.result_ledger import rows_to_dataframe

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


def init_routes(app: flask.Flask, server) -> None:
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
