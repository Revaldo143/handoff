"""
HANDOFF - Model Context Protocol (MCP) Server for Amazon Alexa+ Track.
Exposes intelligent Shift Gatekeeper tools to Alexa+ and AI assistants.
Uses mcp.server.fastmcp to register high-performance agent tools.
"""

import os
import json
import httpx
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("HANDOFF-Gatekeeper-Agent")

API_BASE_URL = os.getenv("HANDOFF_API_URL", "http://127.0.0.1:8000")

def _call_api(method: str, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper to communicate with the FastAPI backend with fast fallback."""
    try:
        with httpx.Client(base_url=API_BASE_URL, timeout=3.0) as client:
            if method.upper() == "POST":
                resp = client.post(path, json=json_data)
            else:
                resp = client.get(path)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        # Fallback to direct database operations if API is offline
        pass

    # Direct database fallback
    from app.database import (
        get_inventory_items,
        get_purchase_orders,
        get_pending_handoff_claims,
        get_connection
    )
    if path == "/api/inventory":
        return {"inventory": get_inventory_items()}
    elif path == "/api/pos":
        return {"purchase_orders": get_purchase_orders()}
    elif path == "/api/handoff/pending":
        return {"pending_claims": get_pending_handoff_claims()}
    elif path == "/api/voice" and json_data:
        # Execute voice processing directly
        import asyncio
        from app.main import process_voice_claim, VoiceRequest
        req = VoiceRequest(text=json_data.get("text", ""), claimant="Alexa+ Voice Assistant")
        return asyncio.run(process_voice_claim(req))

    return {"error": "Could not connect to backend and fallback unhandled"}

@mcp.tool()
def report_issue(text: str, claimant: str = "Alexa Voice Shift Assistant") -> str:
    """
    Report an operational issue or shift handoff claim to the HANDOFF Gatekeeper.
    The Gatekeeper analyzes the claim, queries enterprise records, and either REFUSES or VERIFIES action.
    Examples:
    - 'delivery varala, bread stock is missing'
    - 'cups empty, need restock for morning chai rush'
    """
    payload = {"text": text, "claimant": claimant}
    result = _call_api("POST", "/api/voice", payload)

    # Multi-fragment utterances return {"claims": [...]}
    if result.get("claims"):
        return json.dumps({
            "status": "success",
            "count": result.get("count", len(result["claims"])),
            "claims": [
                {
                    "claim_id": c.get("claim_id"),
                    "gatekeeper_verdict": c.get("gatekeeper_verdict"),
                    "speech_reply": c.get("speech_reply"),
                    "latency_ms": c.get("latency_ms", 0),
                }
                for c in result["claims"]
            ],
            "latency_ms": f"{result.get('latency_ms', 0)} ms",
        }, indent=2)

    verdict = result.get("gatekeeper_verdict", "UNKNOWN")
    speech = result.get("speech_reply", "")
    latency = result.get("latency_ms", 0.0)
    claim_id = result.get("claim_id")
    
    return json.dumps({
        "status": "success",
        "claim_id": claim_id,
        "gatekeeper_verdict": verdict,
        "speech_reply": speech,
        "latency_ms": f"{latency} ms",
        "details": result.get("claim", {})
    }, indent=2)

@mcp.tool()
def check_inventory(item_name_or_sku: str) -> str:
    """
    Check real-time store inventory level and replenishment threshold for Kirana items.
    Checks SKU, unit count, and capacity percentage.
    """
    data = _call_api("GET", "/api/inventory")
    inventory = data.get("inventory", [])
    
    query = item_name_or_sku.lower()
    matches = [
        item for item in inventory
        if query in item["sku"].lower() or query in item["name"].lower() or query in item["category"].lower()
    ]
    
    if not matches:
        return json.dumps({
            "found": False,
            "message": f"No inventory item matching '{item_name_or_sku}' was found in the store ledger.",
            "available_items": [i["name"] for i in inventory]
        }, indent=2)

    return json.dumps({
        "found": True,
        "matches": matches
    }, indent=2)

@mcp.tool()
def check_delivery_receipt(po_number_or_vendor: str) -> str:
    """
    Verify whether a Purchase Order or vendor shipment has an officially logged Goods Received Note (GRN).
    Used to prevent phantom delivery claims and duplicate vendor payments.
    """
    data = _call_api("GET", "/api/pos")
    pos = data.get("purchase_orders", [])
    
    query = po_number_or_vendor.lower()
    matches = [
        po for po in pos
        if query in po["po_number"].lower() or query in po["supplier"].lower() or query in po["item_sku"].lower()
    ]
    
    if not matches:
        return json.dumps({
            "verified_receipt": False,
            "reason": f"No PO or challan found for '{po_number_or_vendor}' in ERP database.",
            "gatekeeper_recommendation": "REFUSE CLAIM - Do not issue emergency payment or duplicate dispatch."
        }, indent=2)
        
    return json.dumps({
        "verified_receipt": any(m.get("receipt_logged") == 1 for m in matches),
        "matching_pos": matches
    }, indent=2)

@mcp.tool()
def get_pending_handoff() -> str:
    """
    Retrieve all unverified or flagged claims that require Morning Shift Store Manager attention.
    Gives morning managers immediate visibility into night-shift anomalies and blocked duplicate attempts.
    """
    data = _call_api("GET", "/api/handoff/pending")
    pending = data.get("pending_claims", [])
    
    return json.dumps({
        "pending_handoff_count": len(pending),
        "claims_requiring_review": pending
    }, indent=2)

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
