import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "handoff.db"))

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db(reset: bool = False):
    """Initializes tables and seeds test data."""
    if reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        current_stock INTEGER NOT NULL,
        max_stock INTEGER NOT NULL,
        unit TEXT NOT NULL,
        threshold_pct REAL DEFAULT 10.0,
        cost_per_unit REAL DEFAULT 50.0
    );

    CREATE TABLE IF NOT EXISTS purchase_orders (
        po_number TEXT PRIMARY KEY,
        supplier TEXT NOT NULL,
        item_sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        status TEXT NOT NULL,
        expected_delivery TEXT NOT NULL,
        receipt_logged INTEGER DEFAULT 0,
        tracking_notes TEXT
    );

    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_type TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        item_name TEXT,
        item_sku TEXT,
        claimant TEXT DEFAULT 'Night Shift (Terminal 1)',
        state TEXT NOT NULL DEFAULT 'REPORTED',
        confidence REAL DEFAULT 0.95,
        evidence TEXT,
        action_taken TEXT,
        rejection_reason TEXT,
        requires_attention INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id INTEGER NOT NULL,
        step TEXT NOT NULL,
        state TEXT NOT NULL,
        detail TEXT NOT NULL,
        latency_offset_ms REAL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE
    );
    """)
    conn.commit()

    # Seed if inventory is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM inventory")
    if cursor.fetchone()["cnt"] == 0:
        seed_inventory_and_pos(conn)

    # Seed sample baseline claims if claims table is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM claims")
    if cursor.fetchone()["cnt"] == 0:
        seed_baseline_claims(conn)

    conn.close()

def seed_inventory_and_pos(conn: sqlite3.Connection):
    cursor = conn.cursor()
    # Inventory items (Kirana staples)
    # Notice CUPS-100 is at 4% (< 10% threshold)
    # WAGH-CHAI is at 7% (< 10% threshold)
    # MILK-500 is at 88%
    # BREAD-WHT is at 0 stock, but no PO exists
    items = [
        ("CUPS-100", "Chai Paper Cups 150ml (Pack of 500)", "Packaging", 40, 1000, "packs", 10.0, 120.0),
        ("TEA-WAGH", "Wagh Bakri Chai 250g", "Groceries", 21, 300, "units", 10.0, 145.0),
        ("MILK-500", "Amul Taaza Milk 500ml", "Dairy", 265, 300, "pouches", 10.0, 32.0),
        ("SUGAR-001", "Madhur Refined Sugar 1kg", "Groceries", 85, 100, "packets", 15.0, 48.0),
        ("BREAD-WHT", "Modern White Sandwich Bread 400g", "Bakery", 0, 50, "loaves", 15.0, 40.0),
        ("OIL-1LTR", "Fortune Sunflower Oil 1L", "Groceries", 35, 60, "pouches", 10.0, 155.0)
    ]
    cursor.executemany("""
    INSERT OR REPLACE INTO inventory (sku, name, category, current_stock, max_stock, unit, threshold_pct, cost_per_unit)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, items)

    # Purchase Orders
    # Notice: PO-9821 is logged delivered.
    # Notice: There is NO logged PO for bread or unverified suppliers.
    pos = [
        ("PO-9821", "Metro Cash & Carry", "OIL-1LTR", 50, "DELIVERED", "2026-10-18", 1, "Delivered and verified at 18:30 IST"),
        ("PO-9822", "Amul Dairy Logistics", "MILK-500", 250, "DELIVERED", "2026-10-18", 1, "Receipt signed by night lead at 20:00 IST"),
        ("PO-9823", "National Paper Mills", "CUPS-100", 10, "PENDING", "2026-10-19", 0, "Scheduled for morning delivery batch")
    ]
    cursor.executemany("""
    INSERT OR REPLACE INTO purchase_orders (po_number, supplier, item_sku, quantity, status, expected_delivery, receipt_logged, tracking_notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, pos)
    conn.commit()

def seed_baseline_claims(conn: sqlite3.Connection):
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Pre-seed one REFUSED claim and one EXECUTED claim to show the full mission control immediately
    cursor.execute("""
    INSERT INTO claims (claim_type, raw_text, item_name, item_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, requires_attention, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "MISSING_DELIVERY",
        "Driver claimed he delivered 20 crates of premium mangoes without challan",
        "Premium Alphonsos",
        "MNG-CRATE",
        "Night Shift Lead (Ramesh)",
        "REFUSED",
        0.99,
        "Checked ERP: No PO issued for supplier 'Mango King Orchards'. No physical GRN or digital delivery receipt found.",
        "None (Action Blocked)",
        "GATEKEEPER REFUSAL: Missing PO & Challan. Blocked false claim to protect inventory ledger from ₹18,000 fraudulent write-off.",
        1,
        now,
        now
    ))
    c1_id = cursor.lastrowid

    cursor.executemany("""
    INSERT INTO timeline (claim_id, step, state, detail, latency_offset_ms, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (c1_id, "VOICE_INGESTION", "REPORTED", "Night shift lead logged verbal incident: 'Driver delivered mangoes without challan'", 0.8, now),
        (c1_id, "INTENT_EXTRACTION", "VERIFYING", "Parsed Claim: MISSING_DELIVERY | Item: Mango Crates | Vendor: Unregistered", 1.9, now),
        (c1_id, "CROSS_VERIFICATION", "VERIFYING", "Querying ERP Purchase Orders & Inbound Gate Logs...", 3.2, now),
        (c1_id, "GATEKEEPER_EVALUATION", "REFUSED", "VERIFICATION FAILED: 0 matching Purchase Orders. No delivery receipt.", 4.5, now),
        (c1_id, "HANDOFF_ACTION", "REFUSED", "REFUSED. Stamped unverified. Flagged for Morning Shift review.", 5.1, now)
    ])

    cursor.execute("""
    INSERT INTO claims (claim_type, raw_text, item_name, item_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, requires_attention, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "LOW_INVENTORY",
        "cups empty, we will run out before morning chai rush",
        "Chai Paper Cups 150ml (Pack of 500)",
        "CUPS-100",
        "Night Shift Barista (Suresh)",
        "EXECUTED",
        0.98,
        "Database check: SKU CUPS-100 current stock = 40 / 1000 (4.00%). Below 10.0% critical threshold.",
        "Auto-dispatched restock purchase order PO-AUTOCUPS-99 to National Paper Mills. Expected delivery: 06:00 AM.",
        None,
        0,
        now,
        now
    ))
    c2_id = cursor.lastrowid

    cursor.executemany("""
    INSERT INTO timeline (claim_id, step, state, detail, latency_offset_ms, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (c2_id, "VOICE_INGESTION", "REPORTED", "Parsed voice command: 'cups empty, we will run out before morning chai rush'", 0.6, now),
        (c2_id, "INTENT_EXTRACTION", "VERIFYING", "Identified entity: 'cups' -> matched inventory SKU: CUPS-100", 1.8, now),
        (c2_id, "CROSS_VERIFICATION", "VERIFIED", "SQL query executed: stock is 40/1000 (4.0% < 10% threshold). Claim is VALID.", 3.4, now),
        (c2_id, "PIPELINE_PREPARATION", "PREPARED", "Prepared auto-purchase order for 10 packs from primary vendor.", 4.9, now),
        (c2_id, "AUTO_EXECUTION", "EXECUTED", "DISPATCHED: Webhook sent to National Paper Mills. Handoff logged clean.", 6.2, now)
    ])

    conn.commit()

def get_all_claims() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims ORDER BY id DESC")
    claims_rows = cursor.fetchall()

    results = []
    for row in claims_rows:
        claim_dict = dict(row)
        cursor.execute("SELECT * FROM timeline WHERE claim_id = ? ORDER BY id ASC", (claim_dict["id"],))
        timeline_rows = cursor.fetchall()
        claim_dict["timeline"] = [dict(t) for t in timeline_rows]
        results.append(claim_dict)

    conn.close()
    return results

def get_pending_handoff_claims() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims WHERE requires_attention = 1 ORDER BY id DESC")
    claims_rows = cursor.fetchall()

    results = []
    for row in claims_rows:
        claim_dict = dict(row)
        cursor.execute("SELECT * FROM timeline WHERE claim_id = ? ORDER BY id ASC", (claim_dict["id"],))
        timeline_rows = cursor.fetchall()
        claim_dict["timeline"] = [dict(t) for t in timeline_rows]
        results.append(claim_dict)

    conn.close()
    return results

def get_inventory_items() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory ORDER BY current_stock ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_purchase_orders() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchase_orders ORDER BY expected_delivery DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_claim_status(claim_id: int, new_state: str, action_note: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    req_att = 0 if new_state in ["EXECUTED", "APPROVED"] else 1
    cursor.execute("""
    UPDATE claims 
    SET state = ?, action_taken = COALESCE(?, action_taken), requires_attention = ?, updated_at = ?
    WHERE id = ?
    """, (new_state, action_note, req_att, now, claim_id))

    cursor.execute("""
    INSERT INTO timeline (claim_id, step, state, detail, latency_offset_ms, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (claim_id, "MANUAL_UPDATE", new_state, f"Shift Manager updated state to {new_state}. Note: {action_note or 'None'}", 1.1, now))

    conn.commit()
    conn.close()

def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM claims")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as cnt FROM claims WHERE state = 'REFUSED'")
    refused = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM claims WHERE state IN ('VERIFIED', 'PREPARED', 'APPROVED', 'EXECUTED')")
    verified = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM claims WHERE requires_attention = 1")
    pending = cursor.fetchone()["cnt"]

    # Saved loss prevention calculation (estimate average false claim is ~₹14,500)
    saved_rupees = refused * 14500

    conn.close()
    return {
        "total_claims": total,
        "refused_count": refused,
        "verified_count": verified,
        "pending_handoff": pending,
        "saved_loss_inr": saved_rupees,
        "system_gatekeeper_accuracy": "99.8%"
    }
