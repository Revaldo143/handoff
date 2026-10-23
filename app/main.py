import time
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import (
    init_db,
    get_connection,
    get_all_claims,
    get_pending_handoff_claims,
    get_inventory_items,
    get_purchase_orders,
    update_claim_status,
    get_stats
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup
    init_db(reset=False)
    yield

app = FastAPI(
    title="HANDOFF - Gatekeeper Shift Agent",
    description="Intelligent Shift Handoff Gatekeeper Agent for Amazon Alexa+ Track",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Streamlit UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VoiceRequest(BaseModel):
    text: str = Field(..., example="the delivery never arrived")
    claimant: Optional[str] = "Night Shift Operator"
    shift: Optional[str] = "Night Shift -> Morning Shift"

class ActionRequest(BaseModel):
    state: str = Field(..., example="APPROVED")
    note: Optional[str] = None

@app.get("/")
def read_root():
    return {
        "system": "HANDOFF Gatekeeper Agent",
        "tagline": "Every agent acts. This one knows when NOT to.",
        "status": "ONLINE",
        "version": "1.0.0",
        "alexa_plus_compatible": True
    }

def _process_fragment(fragment_text: str, claimant: str, conn, t_start: float):
    """
    Process ONE utterance fragment into ONE claim: intent classification,
    gatekeeper cross-verification against SQLite, state machine, thinking trace.
    Returns the single-claim response dict (same shape /api/voice uses for one claim).
    """
    raw_text = fragment_text.strip()
    lowered = raw_text.lower()

    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    trace_log = []
    
    def log_trace(step: str, state: str, detail: str):
        elapsed = (time.perf_counter() - t_start) * 1000.0
        trace_log.append({
            "step": step,
            "state": state,
            "detail": detail,
            "latency_offset_ms": round(elapsed, 2),
            "created_at": datetime.now().isoformat()
        })

    log_trace("VOICE_INGESTION", "REPORTED", f"Incoming voice payload received: '{raw_text}'")
    log_trace("TEXT_PARSE", "REPORTED", f"Text input parsed (English) from {claimant}")

    # Determine intent & entities
    is_delivery_issue = any(k in lowered for k in [
        "delivery", "varala", "did not arrive", "didn't arrive", "driver", 
        "challan", "vendor missing", "not received", "missing delivery", "parsal"
    ])
    is_inventory_issue = any(k in lowered for k in [
        "cup", "cups", "empty", "theerndhudhu", "stock", "tea", "chai", 
        "milk", "sugar", "bread", "oil", "exhausted", "koraiva", "depleted", "low"
    ])

    claim_id = None
    response_decision = {}

    if is_delivery_issue and not ("cups" in lowered and "empty" in lowered and not "varala" in lowered):
        # Scenario 1: Delivery Issue (e.g. "the delivery never arrived")
        log_trace("INTENT_EXTRACTION", "VERIFYING", "Intent classified as: MISSING_DELIVERY | Priority: HIGH")
        
        # Check if an item is specified or if general delivery is claimed
        matched_item = "Daily Fresh Bread & Bakery"
        item_sku = "BREAD-WHT"
        if "milk" in lowered:
            matched_item = "Amul Milk 500ml"
            item_sku = "MILK-500"
        elif "oil" in lowered:
            matched_item = "Fortune Sunflower Oil"
            item_sku = "OIL-1LTR"
        elif "biscuit" in lowered:
            matched_item = "Parle-G Biscuits"
            item_sku = "BISCUIT-PARLE"

        log_trace("ENTITY_EXTRACTION", "VERIFYING", f"Extracted target entity: '{matched_item}' (Inferred SKU: {item_sku})")
        log_trace("ERP_LOOKUP", "VERIFYING", f"Executing fast query on purchase_orders for item {item_sku}...")

        # Query PO database
        cursor.execute("SELECT * FROM purchase_orders WHERE item_sku = ?", (item_sku,))
        po_row = cursor.fetchone()

        # Gatekeeper evaluation:
        # If no receipt was logged, or no active PO exists for this expected delivery, REFUSE!
        # Kirana reality: Shift workers often claim "delivery didn't come" for items that weren't even ordered or already arrived yesterday.
        if not po_row:
            log_trace("GATEKEEPER_EVAL", "REFUSED", f"ERP Check Result: 0 Purchase Orders found for '{matched_item}'.")
            log_trace("FRAUD_PREVENTION", "REFUSED", "GATEKEEPER REFUSAL TRIGGERED: No active PO or dispatch record exists.")
            
            rejection_reason = "No active Purchase Order or dispatched challan exists in ERP. Shift worker claim rejected to prevent duplicate order and phantom invoice write-off."
            evidence = f"Checked ERP database: 0 PO records found for {matched_item}. No supplier dispatch recorded for this shift."
            action_taken = "ACTION BLOCKED by Gatekeeper: Prevented unauthorized emergency purchase order of ₹12,000. Flagged for Morning Shift Manager."
            state = "REFUSED"
            confidence = 0.99
            speech_reply = f"Handoff Gatekeeper refused this claim. No purchase order exists for {matched_item}. Duplicate re-order blocked."
        else:
            po = dict(po_row)
            if po["receipt_logged"] == 1:
                log_trace("GATEKEEPER_EVAL", "REFUSED", f"ERP Check Result: PO {po['po_number']} was ALREADY DELIVERED & signed at {po['tracking_notes']}.")
                log_trace("GATEKEEPER_REFUSAL", "REFUSED", "GATEKEEPER REFUSAL TRIGGERED: Item already verified in warehouse. False missing claim.")
                
                rejection_reason = f"Purchase Order {po['po_number']} was already marked DELIVERED and receipt confirmed in system. Shift worker reported missing in error."
                evidence = f"PO {po['po_number']} confirmed delivered with physical receipt logged: {po['tracking_notes']}."
                action_taken = "ACTION BLOCKED: Directed night staff to secondary shelf storage. Prevented double billing."
                state = "REFUSED"
                confidence = 0.98
                speech_reply = f"Claim refused. Purchase Order {po['po_number']} was already received and verified in stock. Check secondary storage."
            else:
                log_trace("GATEKEEPER_EVAL", "VERIFIED", f"ERP Check Result: PO {po['po_number']} is pending dispatch from {po['supplier']}.")
                rejection_reason = None
                evidence = f"Verified: PO {po['po_number']} is overdue from {po['supplier']}. Inbound shipment delayed."
                action_taken = f"Auto-escalated delayed shipment alert to vendor {po['supplier']} via SMS/WhatsApp gateway."
                state = "VERIFIED"
                confidence = 0.96
                speech_reply = f"Claim verified. Supplier {po['supplier']} has delayed shipment on PO {po['po_number']}. Automated vendor escalation dispatched."

        # Insert claim
        cursor.execute("""
        INSERT INTO claims (claim_type, raw_text, item_name, item_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, requires_attention, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "MISSING_DELIVERY", raw_text, matched_item, item_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, 1 if state == "REFUSED" else 0, now_iso, now_iso
        ))
        claim_id = cursor.lastrowid

    elif is_inventory_issue:
        # Scenario 2: Inventory Issue (e.g. "cups empty")
        log_trace("INTENT_EXTRACTION", "VERIFYING", "Intent classified as: LOW_INVENTORY | Priority: IMMEDIATE")
        
        # Match SKU (prioritize cup matches before generic chai)
        if "cup" in lowered:
            target_sku = "CUPS-100"
            target_name = "Chai Paper Cups 150ml (Pack of 500)"
        elif "tea" in lowered or "chai" in lowered or "wagh" in lowered:
            target_sku = "TEA-WAGH"
            target_name = "Wagh Bakri Chai 250g"
        elif "milk" in lowered:
            target_sku = "MILK-500"
            target_name = "Amul Taaza Milk 500ml"
        elif "sugar" in lowered:
            target_sku = "SUGAR-001"
            target_name = "Madhur Refined Sugar 1kg"
        elif "oil" in lowered:
            target_sku = "OIL-1LTR"
            target_name = "Fortune Sunflower Oil 1L"
        elif "bread" in lowered:
            target_sku = "BREAD-WHT"
            target_name = "Modern White Bread 400g"
        else:
            # No catalog SKU matched the utterance (e.g. "stock is low").
            # Refuse gracefully instead of crashing on an unbound variable.
            target_sku = None
            target_name = "Unknown item"

        log_trace("ENTITY_EXTRACTION", "VERIFYING", f"Target identified: '{target_name}' (SKU: {target_sku})")
        log_trace("SQL_STOCK_QUERY", "VERIFYING", f"Querying live inventory ledger for {target_sku}...")

        cursor.execute("SELECT * FROM inventory WHERE sku = ?", (target_sku,))
        inv_row = cursor.fetchone()

        if not inv_row:
            log_trace("GATEKEEPER_EVAL", "REFUSED", f"Item SKU '{target_sku}' not recognized in store catalog.")
            state = "REFUSED"
            rejection_reason = "Unregistered SKU. Cannot automate re-order for untracked catalog item."
            evidence = "Inventory ledger returned NULL record for item."
            action_taken = "BLOCKED: Logged untracked item query for store inventory audit."
            confidence = 0.92
            speech_reply = f"Claim refused. Item {target_name} is not recognized in active store catalog."
        else:
            inv = dict(inv_row)
            current_stock = inv["current_stock"]
            max_stock = inv["max_stock"]
            ratio = (current_stock / max_stock) * 100.0
            threshold = inv["threshold_pct"]

            log_trace("METRIC_CALCULATION", "VERIFYING", f"Stock metric: {current_stock}/{max_stock} ({ratio:.1f}%). Reorder threshold = {threshold:.1f}%.")

            if ratio < threshold:
                # Verified: genuinely below the critical threshold
                log_trace("GATEKEEPER_EVAL", "VERIFIED", f"CRITICAL SHORTAGE VERIFIED: Stock ratio ({ratio:.1f}%) < threshold ({threshold:.1f}%).")
                log_trace("PIPELINE_PREPARE", "PREPARED", f"Drafted restocking Purchase Order: 10 {inv['unit']} of {inv['name']}.")
                log_trace("AUTO_EXECUTION", "EXECUTED", f"Automated PO dispatched to vendor via B2B API. Scheduled delivery: 05:30 AM.")
                
                state = "EXECUTED"
                rejection_reason = None
                evidence = f"Live inventory check: Current stock is {current_stock} {inv['unit']} ({ratio:.1f}% of capacity {max_stock}). Critical limit is {threshold}%."
                action_taken = f"AUTO-EXECUTED: Created and dispatched urgent PO to supplier for 10 {inv['unit']}. Morning rush protected."
                confidence = 0.99
                speech_reply = f"Verified: {inv['name']} is at {ratio:.1f}% stock. Restock order for 10 {inv['unit']} has been automatically placed for 5:30 AM delivery."
            else:
                # Stock is adequate -> Gatekeeper refuses unnecessary restock!
                log_trace("GATEKEEPER_EVAL", "REFUSED", f"Stock level ({ratio:.1f}%) is well ABOVE threshold ({threshold:.1f}%). Sufficient units ({current_stock}).")
                log_trace("BUDGET_GUARD", "REFUSED", "GATEKEEPER REFUSAL TRIGGERED: Blocked redundant restock to prevent over-purchasing.")
                
                state = "REFUSED"
                rejection_reason = f"Inventory level is healthy at {ratio:.1f}%, exceeding the {threshold}% minimum replenishment threshold. Restock refused."
                evidence = f"Store shelf count: {current_stock}/{max_stock} units available ({ratio:.1f}%). Threshold is {threshold}%."
                action_taken = "ACTION BLOCKED: Refused duplicate restock request. Preserved working capital."
                confidence = 0.97
                speech_reply = f"Restock request refused. {inv['name']} is at {ratio:.1f}% capacity with {current_stock} units on shelf. No restock needed."

        cursor.execute("""
        INSERT INTO claims (claim_type, raw_text, item_name, item_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, requires_attention, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "LOW_INVENTORY", raw_text, target_name, target_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, 1 if state == "REFUSED" else 0, now_iso, now_iso
        ))
        claim_id = cursor.lastrowid

    else:
        # Scenario 3: General / Operational note
        log_trace("INTENT_EXTRACTION", "VERIFYING", "Intent classified as: GENERAL_NOTE / SHIFT_ANOMALY")
        log_trace("GATEKEEPER_EVAL", "REFUSED", "No verifiable inventory metric or Purchase Order associated with claim.")
        
        state = "REFUSED"
        confidence = 0.85
        evidence = "Acoustic input lacks structured operational entities (SKU or PO#)."
        rejection_reason = "Unsubstantiated shift verbal report. Lacks verifiable database backing."
        action_taken = "ACTION BLOCKED: Logged to shift audit notes for morning review without executing changes."
        speech_reply = "Note received, but automated action was refused because no verified invoice or inventory entity was matched."

        cursor.execute("""
        INSERT INTO claims (claim_type, raw_text, item_name, item_sku, claimant, state, confidence, evidence, action_taken, rejection_reason, requires_attention, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "GENERAL", raw_text, "Store Operations", "GEN-01", claimant, state, confidence, evidence, action_taken, rejection_reason, 1, now_iso, now_iso
        ))
        claim_id = cursor.lastrowid

    # Insert timeline traces into DB
    for entry in trace_log:
        cursor.execute("""
        INSERT INTO timeline (claim_id, step, state, detail, latency_offset_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (claim_id, entry["step"], entry["state"], entry["detail"], entry["latency_offset_ms"], entry["created_at"]))

    conn.commit()

    # Retrieve full inserted claim
    cursor.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
    full_claim = dict(cursor.fetchone())
    cursor.execute("SELECT * FROM timeline WHERE claim_id = ? ORDER BY id ASC", (claim_id,))
    full_claim["timeline"] = [dict(t) for t in cursor.fetchall()]

    total_latency = round((time.perf_counter() - t_start) * 1000.0, 2)

    return {
        "status": "success",
        "claim_id": claim_id,
        "state": full_claim["state"],
        "speech_reply": speech_reply,
        "claim": full_claim,
        "latency_ms": total_latency,
        "gatekeeper_verdict": full_claim["state"]
    }


@app.post("/api/voice")
async def process_voice_claim(payload: VoiceRequest):
    """
    Main voice/text intake endpoint.
    Splits multi-part utterances ("freezer delivery never arrived, cups are almost empty")
    into fragments; each fragment becomes its own claim with its own verdict.
    Single-fragment input keeps the exact original single-claim response shape.
    """
    t_start = time.perf_counter()
    claimant = payload.claimant or "Night Shift Operator"

    fragments = [f.strip() for f in re.split(r"[,;]|\s\+\s", payload.text.strip()) if f.strip()]
    seen, frags = set(), []
    for f in fragments:
        if f.lower() not in seen:
            seen.add(f.lower())
            frags.append(f)
    if not frags:
        raise HTTPException(status_code=400, detail="empty utterance")

    conn = get_connection()
    try:
        results = [_process_fragment(f, claimant, conn, t_start) for f in frags]
        conn.commit()
    finally:
        conn.close()

    total_latency = round((time.perf_counter() - t_start) * 1000.0, 2)

    if len(results) == 1:
        results[0]["latency_ms"] = total_latency
        return results[0]

    return {
        "status": "success",
        "claims": results,
        "count": len(results),
        "latency_ms": total_latency,
        "speech_reply": " ".join(r["speech_reply"] for r in results),
        "gatekeeper_verdict": "MULTI",
    }

@app.get("/api/claims")
def list_claims():
    """Returns all claims with complete state machine timeline."""
    t_start = time.perf_counter()
    claims = get_all_claims()
    latency = round((time.perf_counter() - t_start) * 1000.0, 2)
    return {
        "count": len(claims),
        "claims": claims,
        "latency_ms": latency
    }

@app.get("/api/handoff/pending")
def list_pending_handoff():
    """Returns claims that need morning shift attention."""
    t_start = time.perf_counter()
    pending = get_pending_handoff_claims()
    latency = round((time.perf_counter() - t_start) * 1000.0, 2)
    return {
        "count": len(pending),
        "pending_claims": pending,
        "latency_ms": latency,
        "shift_window": "Night Shift -> Morning Shift Handoff"
    }

@app.post("/api/claims/{claim_id}/approve")
def approve_claim(claim_id: int, req: Optional[ActionRequest] = None):
    note = req.note if req else "Manually approved by Morning Shift Store Manager"
    update_claim_status(claim_id, "APPROVED", note)
    return {"status": "success", "claim_id": claim_id, "state": "APPROVED"}

@app.post("/api/claims/{claim_id}/refuse")
def refuse_claim(claim_id: int, req: Optional[ActionRequest] = None):
    note = req.note if req else "Refusal affirmed by Morning Shift Store Manager"
    update_claim_status(claim_id, "REFUSED", note)
    return {"status": "success", "claim_id": claim_id, "state": "REFUSED"}

@app.post("/api/claims/{claim_id}/execute")
def execute_claim(claim_id: int, req: Optional[ActionRequest] = None):
    note = req.note if req else "Execution triggered by Morning Shift Store Manager"
    update_claim_status(claim_id, "EXECUTED", note)
    return {"status": "success", "claim_id": claim_id, "state": "EXECUTED"}

@app.get("/api/inventory")
def list_inventory():
    items = get_inventory_items()
    return {"inventory": items, "count": len(items)}

@app.get("/api/pos")
def list_pos():
    pos = get_purchase_orders()
    return {"purchase_orders": pos, "count": len(pos)}

@app.get("/api/stats")
def dashboard_stats():
    stats = get_stats()
    return stats

@app.post("/api/reset")
def reset_demo():
    """Resets database to pristine seed state for clean live demos."""
    init_db(reset=True)
    return {"status": "success", "message": "Database refreshed with clean seed dataset."}
