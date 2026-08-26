# -*- coding: utf-8 -*-
"""
SQLite database backend for concurrent multi-device access.
"""
import sqlite3
import threading
import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class Database:
    """Thread-safe SQLite database for results storage."""

    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        if db_path is None:
            # Default to user's data directory
            data_dir = Path.home() / ".gearledger" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "gearledger.db")

        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
            )
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA busy_timeout=30000")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create results table. sale_price is part of the UNIQUE
        # constraint (not just artikul+client) so that when the same
        # client has multiple catalog lines for the same article at
        # different prices, each price tier can have its own row instead
        # of being forced into one — see allocate_tiered_quantity in
        # result_ledger.py for why.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artikul TEXT NOT NULL,
                client TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                weight REAL DEFAULT 0,
                last_updated TEXT,
                brand TEXT DEFAULT '',
                description TEXT DEFAULT '',
                sale_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artikul, client, sale_price)
            )
        """
        )

        # Create index for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_artikul_client
            ON results(artikul, client)
        """
        )

        conn.commit()

        self._migrate_unique_constraint_if_needed(cursor, conn)

    def _migrate_unique_constraint_if_needed(self, cursor, conn):
        """A database created before tiered pricing existed has
        UNIQUE(artikul, client) with no sale_price — inserting a second
        price tier for the same artikul+client would violate that old
        constraint with a raw sqlite3.IntegrityError. Detect it and
        migrate the table in place (rename, recreate with the new
        constraint, copy rows, drop the old one). Copying is always safe
        here: widening a UNIQUE constraint with an extra column can only
        ever reduce collisions, never introduce new ones.
        """
        cursor.execute("PRAGMA index_list('results')")
        needs_migration = False
        found_any_unique_index = False
        for idx in cursor.fetchall():
            # idx columns: (seq, name, unique, origin, partial)
            if not idx[2]:
                continue
            cursor.execute(f"PRAGMA index_info('{idx[1]}')")
            cols = {row[2] for row in cursor.fetchall()}
            if cols == {"artikul", "client"}:
                found_any_unique_index = True
                needs_migration = True
            elif cols == {"artikul", "client", "sale_price"}:
                found_any_unique_index = True
                needs_migration = False

        if not found_any_unique_index or not needs_migration:
            return

        print(
            "[DATABASE] Migrating results table: "
            "UNIQUE(artikul, client) -> UNIQUE(artikul, client, sale_price)"
        )
        cursor.execute("ALTER TABLE results RENAME TO results_pre_tier_migration")
        cursor.execute(
            """
            CREATE TABLE results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artikul TEXT NOT NULL,
                client TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                weight REAL DEFAULT 0,
                last_updated TEXT,
                brand TEXT DEFAULT '',
                description TEXT DEFAULT '',
                sale_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artikul, client, sale_price)
            )
        """
        )
        cursor.execute(
            """
            INSERT INTO results
                (id, artikul, client, quantity, weight, last_updated,
                 brand, description, sale_price, total_price, created_at)
            SELECT id, artikul, client, quantity, weight, last_updated,
                   brand, description, sale_price, total_price, created_at
            FROM results_pre_tier_migration
        """
        )
        cursor.execute("DROP TABLE results_pre_tier_migration")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_artikul_client ON results(artikul, client)"
        )
        conn.commit()
        print("[DATABASE] Migration complete")

    def add_or_update_result(
        self,
        artikul: str,
        client: str,
        quantity: int = 1,
        weight: float = 0,
        brand: str = "",
        description: str = "",
        sale_price: float = 0,
    ) -> Dict[str, Any]:
        """
        Add a new result or update existing one.
        If item exists for client, increment quantity (not weight).
        """
        print(f"[DATABASE] add_or_update_result called:")
        print(f"[DATABASE]   artikul={artikul}, client={client}")
        print(f"[DATABASE]   quantity={quantity}, weight={weight}, price={sale_price}")

        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Check if exists (normalization comparison done in Python, see
        # _find_by_key, so it can't drift out of sync with a hand-written
        # SQL REPLACE() chain)
        existing = self._find_by_key(cursor, artikul, client)
        print(f"[DATABASE]   existing record: {dict(existing) if existing else None}")

        if existing:
            # Update existing - increment quantity only, keep weight
            new_quantity = existing["quantity"] + quantity
            # Use new price if provided, else keep existing
            final_price = sale_price if sale_price > 0 else existing["sale_price"]
            total = final_price * new_quantity
            print(
                f"[DATABASE]   UPDATING: new_quantity={new_quantity}, price={final_price}"
            )

            cursor.execute(
                """
                UPDATE results 
                SET quantity = ?, 
                    last_updated = ?,
                    sale_price = ?,
                    total_price = ?,
                    brand = COALESCE(NULLIF(?, ''), brand),
                    description = COALESCE(NULLIF(?, ''), description)
                WHERE id = ?
                """,
                (
                    new_quantity,
                    now,
                    final_price,
                    total,
                    brand,
                    description,
                    existing["id"],
                ),
            )
            conn.commit()
            print(f"[DATABASE]   UPDATE committed, id={existing['id']}")
            return {"ok": True, "action": "updated", "id": existing["id"]}
        else:
            # Insert new
            total = sale_price * quantity
            print(f"[DATABASE]   INSERTING new record: total={total}")
            cursor.execute(
                """
                INSERT INTO results 
                (artikul, client, quantity, weight, last_updated, brand, description, sale_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artikul,
                    client,
                    quantity,
                    weight,
                    now,
                    brand,
                    description,
                    sale_price,
                    total,
                ),
            )
            conn.commit()
            print(f"[DATABASE]   INSERT committed, id={cursor.lastrowid}")
            return {"ok": True, "action": "inserted", "id": cursor.lastrowid}

    def add_or_update_result_tiered(
        self,
        artikul: str,
        client: str,
        quantity: int = 1,
        weight: float = 0,
        tiers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Record a scan using catalog price tiers instead of a single
        pre-resolved price — mirrors result_ledger.record_match's
        allocation logic (see allocate_tiered_quantity) so server mode
        gets the same correct-per-tier pricing as standalone/Excel mode:
        when the same client has multiple catalog lines for this artikul
        at different prices, quantity fills the first tier's ordered
        amount before spilling into the next tier's price, each landing
        in its own row. With zero or one distinct-priced tier (the
        common case), this behaves exactly like add_or_update_result.
        """
        from .result_ledger import allocate_tiered_quantity, price_key

        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        def _existing_qty_at_price(price) -> int:
            artikul_norm = self._normalize(artikul)
            cursor.execute(
                "SELECT quantity, artikul, sale_price FROM results WHERE UPPER(client) = UPPER(?)",
                (client,),
            )
            total = 0
            for row in cursor.fetchall():
                if (
                    self._normalize(row["artikul"]) == artikul_norm
                    and price_key(row["sale_price"]) == price_key(price)
                ):
                    total += row["quantity"] or 0
            return total

        allocations = allocate_tiered_quantity(
            quantity, tiers or [], _existing_qty_at_price
        )
        print(f"[DATABASE] add_or_update_result_tiered: {artikul}/{client} qty={quantity} -> {allocations}")

        any_inserted = False
        last_id = None
        for alloc in allocations:
            alloc_qty = alloc["qty"]
            if alloc_qty <= 0:
                continue
            alloc_price = alloc["цена"]
            existing = self._find_by_key(cursor, artikul, client, price=alloc_price)

            if existing:
                new_quantity = existing["quantity"] + alloc_qty
                total = alloc_price * new_quantity
                cursor.execute(
                    """
                    UPDATE results
                    SET quantity = ?,
                        last_updated = ?,
                        sale_price = ?,
                        total_price = ?,
                        brand = COALESCE(NULLIF(?, ''), brand),
                        description = COALESCE(NULLIF(?, ''), description)
                    WHERE id = ?
                    """,
                    (
                        new_quantity,
                        now,
                        alloc_price,
                        total,
                        alloc["бренд"],
                        alloc["описание"],
                        existing["id"],
                    ),
                )
                last_id = existing["id"]
            else:
                total = alloc_price * alloc_qty
                cursor.execute(
                    """
                    INSERT INTO results
                    (artikul, client, quantity, weight, last_updated, brand, description, sale_price, total_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artikul,
                        client,
                        alloc_qty,
                        weight,
                        now,
                        alloc["бренд"],
                        alloc["описание"],
                        alloc_price,
                        total,
                    ),
                )
                last_id = cursor.lastrowid
                any_inserted = True

        conn.commit()
        return {
            "ok": True,
            "action": "inserted" if any_inserted else "updated",
            "id": last_id,
        }

    def get_all_results(self, client: str = None) -> List[Dict[str, Any]]:
        """Get all results, optionally filtered by client."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if client:
            cursor.execute(
                """
                SELECT * FROM results 
                WHERE UPPER(client) = UPPER(?)
                ORDER BY last_updated DESC
                """,
                (client,),
            )
        else:
            cursor.execute("SELECT * FROM results ORDER BY last_updated DESC")

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_result_by_id(self, result_id: int) -> Optional[Dict[str, Any]]:
        """Get a single result by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_result(self, result_id: int, **kwargs) -> bool:
        """Update specific fields of a result."""
        conn = self._get_connection()
        cursor = conn.cursor()

        allowed_fields = [
            "artikul",
            "client",
            "quantity",
            "weight",
            "brand",
            "description",
            "sale_price",
            "total_price",
        ]

        updates = []
        values = []
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if not updates:
            return False

        updates.append("last_updated = ?")
        values.append(datetime.datetime.now().isoformat())
        values.append(result_id)

        cursor.execute(
            f"UPDATE results SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_result(self, result_id: int) -> bool:
        """Delete a result by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _find_by_key(self, cursor, artikul: str, client: str, price: float = None):
        """Find a results row matching (artikul, client) — and, when
        `price` is given, that exact price tier too, since the same
        artikul+client can now have multiple rows at different prices
        (see the UNIQUE(artikul, client, sale_price) migration above).
        `price=None` returns the first match regardless of price,
        preserving old behavior for callers that aren't tier-aware yet.

        Does the normalization comparison in Python (via self._normalize)
        instead of duplicating it as a hand-written SQL REPLACE() chain —
        three separate copies of that chain drifting out of sync with the
        Python-side normalizer was exactly how this class of bug happened
        before, so there's now exactly one place to update.
        """
        from .result_ledger import price_key

        artikul_norm = self._normalize(artikul)
        cursor.execute(
            "SELECT * FROM results WHERE UPPER(client) = UPPER(?)",
            (client,),
        )
        for row in cursor.fetchall():
            if self._normalize(row["artikul"]) != artikul_norm:
                continue
            if price is not None and price_key(row["sale_price"]) != price_key(price):
                continue
            return row
        return None

    def delete_result_by_key(self, artikul: str, client: str, price: float = None) -> int:
        """Delete the result row matching (artikul, client) — and, when
        `price` is given, that exact price tier's row (the same
        artikul+client can have several rows at different prices; see
        the UNIQUE(artikul, client, sale_price) migration). Without
        price, matches the first row found regardless of price (existing
        behavior, unchanged). Returns rows deleted."""
        conn = self._get_connection()
        cursor = conn.cursor()
        row = self._find_by_key(cursor, artikul, client, price=price)
        if not row:
            return 0
        cursor.execute("DELETE FROM results WHERE id = ?", (row["id"],))
        conn.commit()
        return cursor.rowcount

    def update_result_quantity_by_key(
        self, artikul: str, client: str, new_quantity: int, price: float = None
    ) -> bool:
        """Set the recorded quantity for (artikul, client) — and, when
        `price` is given, that exact price tier's row — recomputing
        total_price from the existing per-unit sale_price. Returns True if a
        row was updated."""
        conn = self._get_connection()
        cursor = conn.cursor()
        row = self._find_by_key(cursor, artikul, client, price=price)
        if not row:
            return False
        total = (row["sale_price"] or 0) * new_quantity
        cursor.execute(
            "UPDATE results SET quantity = ?, total_price = ?, last_updated = ? WHERE id = ?",
            (new_quantity, total, datetime.datetime.now().isoformat(), row["id"]),
        )
        conn.commit()
        return cursor.rowcount > 0

    def clear_all_results(self, client: str = None) -> int:
        """Clear all results, optionally for a specific client."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if client:
            cursor.execute(
                "DELETE FROM results WHERE UPPER(client) = UPPER(?)",
                (client,),
            )
        else:
            cursor.execute("DELETE FROM results")

        conn.commit()
        return cursor.rowcount

    def archive_results_before_clear(self, versions_dir: str, client: str = None) -> int:
        """Export current results to an Excel version file, then clear them.

        Used by server/client-mode Reset so a database wipe gets the same
        version-history safety net as the standalone Excel file does. Skips
        creating the archive (but still clears) if the current data is
        unchanged since the last Restore — otherwise restoring back and
        forth with nothing recorded in between piles up duplicate versions.

        Returns the number of rows cleared.
        """
        rows = self.get_all_results(client)
        if rows and not self._is_redundant_of_last_restore(rows, versions_dir):
            from .result_ledger import rows_to_dataframe, unique_version_path

            df = rows_to_dataframe(rows)
            df.to_excel(unique_version_path(versions_dir), index=False)
        return self.clear_all_results(client)

    def _is_redundant_of_last_restore(self, current_rows: list, versions_dir: str) -> bool:
        """True if current_rows are unchanged since the last Restore — i.e.
        archiving them now would just duplicate the version already
        restored from.

        Deliberately restore-only, not import: an imported file can live
        anywhere on disk (outside our control — the user could move/delete
        it), so import always creates its own internal version copy rather
        than relying on the external source file staying put.
        """
        try:
            import os

            from .desktop.settings_manager import load_settings
            from .result_ledger import get_all_results_excel, rows_equal

            settings = load_settings()
            if settings.last_results_action != "restore":
                return False
            source_path = os.path.join(
                versions_dir, settings.last_results_action_detail
            )
            if not os.path.exists(source_path):
                return False
            return rows_equal(current_rows, get_all_results_excel(source_path))
        except Exception:
            return False

    def restore_from_version(self, version_path: str, versions_dir: str) -> Dict[str, Any]:
        """Replace current DB results with the contents of an archived
        version file, archiving whatever's currently active first (same
        safety net Reset uses) so nothing is lost in the swap.

        Returns {"ok", "error", "restored"} — restored is the row count
        loaded from the version file.
        """
        if not Path(version_path).exists():
            return {"ok": False, "error": "Version file not found", "restored": 0}

        from .result_ledger import get_all_results_excel

        try:
            rows = get_all_results_excel(version_path)
        except Exception as e:
            return {"ok": False, "error": str(e), "restored": 0}

        self.archive_results_before_clear(versions_dir)

        conn = self._get_connection()
        cursor = conn.cursor()
        for r in rows:
            cursor.execute(
                """
                INSERT INTO results
                (artikul, client, quantity, weight, last_updated, brand, description, sale_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.get("artikul", ""),
                    r.get("client", ""),
                    r.get("quantity", 0),
                    r.get("weight", 0),
                    str(r.get("last_updated", "") or ""),
                    r.get("brand", ""),
                    r.get("description", ""),
                    r.get("sale_price", 0),
                    r.get("total_price", 0),
                ),
            )
        conn.commit()
        return {"ok": True, "error": None, "restored": len(rows)}

    def get_clients(self) -> List[str]:
        """Get list of unique clients."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT client FROM results ORDER BY client")
        return [row[0] for row in cursor.fetchall()]

    def has_any_results(self) -> bool:
        """Cheap existence check for the one-time standalone-storage
        migration gate — avoids pulling every row just to test emptiness."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM results LIMIT 1")
        return cursor.fetchone() is not None

    def export_to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export all data grouped by client for Excel export."""
        results = self.get_all_results()
        by_client = {}
        for r in results:
            client = r["client"]
            if client not in by_client:
                by_client[client] = []
            by_client[client].append(r)
        return by_client

    def _normalize(self, s: str) -> str:
        """Normalize string for matching — delegates to the single shared
        normalizer (result_ledger._norm) instead of keeping its own copy."""
        from .result_ledger import _norm

        return _norm(s)

    def close(self):
        """Close database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Global database instance
_db_instance: Optional[Database] = None


def get_database(db_path: str = None) -> Database:
    """Get or create global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance


def reset_database():
    """Reset database instance (for testing or switching modes)."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
    _db_instance = None
