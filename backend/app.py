import asyncio
import hashlib
import json
import os
import requests
import secrets
import time
from urllib.parse import urlencode
import logging
from typing import List, Dict, Any, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.engine.scanner import BreakoutScanner
from backend.adapters.simulator import MarketSimulatorAdapter
from backend.adapters.fyers_adapter import FyersAdapter
from backend.adapters.kite_adapter import KiteAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fno_scanner")

app = FastAPI(title="FnO Pulse Scanner API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
active_adapter_name = settings.ACTIVE_ADAPTER if settings.ACTIVE_ADAPTER in {"simulator", "fyers", "kite"} else "simulator"
adapters = {
    "simulator": MarketSimulatorAdapter(),
    "fyers": FyersAdapter(settings.FYERS_APP_ID, settings.FYERS_ACCESS_TOKEN),
    "kite": KiteAdapter()
}

scanner = BreakoutScanner(
    pe_surge_threshold=settings.PE_OI_SURGE_THRESHOLD_PCT,
    ce_surge_threshold=settings.CE_OI_SURGE_THRESHOLD_PCT,
    writer_proximity_pct=settings.WRITER_PROXIMITY_PCT,
    volume_surge_multiplier=settings.VOLUME_SURGE_MULTIPLIER
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for d in dead:
            self.active_connections.discard(d)

manager = ConnectionManager()
fyers_oauth_state = ""
scanner_task: Optional[asyncio.Task] = None


@app.get("/api/auth/fyers/login")
async def fyers_login():
    """Start Fyers OAuth and redirect the user to the Fyers login page."""
    global fyers_oauth_state
    if not settings.FYERS_APP_ID or not settings.FYERS_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="FYERS_APP_ID and FYERS_SECRET_KEY must be configured"
        )

    fyers_oauth_state = secrets.token_urlsafe(24)
    params = urlencode({
        "client_id": settings.FYERS_APP_ID,
        "redirect_uri": settings.FYERS_REDIRECT_URI,
        "response_type": "code",
        "state": fyers_oauth_state,
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        f"https://api-t1.fyers.in/api/v3/generate-authcode?{params}"
    )


@app.get("/api/auth/fyers/callback")
async def fyers_callback(
    auth_code: str = "",
    state: str = "",
    s: str = "",
    code: str = "",
    error: str = "",
):
    """Exchange the one-time Fyers authorization code for an access token."""
    if error:
        raise HTTPException(status_code=400, detail=f"Fyers authorization failed: {error}")
    received_code = auth_code or s or code
    if not received_code:
        raise HTTPException(
            status_code=400,
            detail="Missing Fyers authorization code. Start at /api/auth/fyers/login."
        )
    if fyers_oauth_state and state != fyers_oauth_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if not settings.FYERS_APP_ID or not settings.FYERS_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Fyers credentials are not configured")

    app_id_hash = hashlib.sha256(
        f"{settings.FYERS_APP_ID}:{settings.FYERS_SECRET_KEY}".encode()
    ).hexdigest()
    response = await asyncio.to_thread(
        requests.post,
        "https://api-t1.fyers.in/api/v3/validate-authcode",
        json={
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": received_code,
        },
        timeout=10,
    )
    data = response.json()
    if response.status_code != 200 or data.get("s") != "ok":
        raise HTTPException(status_code=400, detail=data)

    access_token = data.get("access_token", "")
    adapters["fyers"].update_credentials({
        "app_id": settings.FYERS_APP_ID,
        "access_token": access_token,
    })
    settings.FYERS_ACCESS_TOKEN = access_token
    await adapters["fyers"].start()
    return {
        "status": "success",
        "message": "Token generated. Add this value to Railway as FYERS_ACCESS_TOKEN.",
        "access_token": access_token,
    }

# Background Scanner Broadcast Loop
async def scanner_broadcast_loop():
    logger.info("Starting real-time scanner broadcast loop...")
    while True:
        try:
            adapter = adapters.get(active_adapter_name)
            if adapter and adapter.is_connected:
                snapshots = adapter.get_market_snapshots()
                
                scanned_results = []
                all_signals = []
                all_surges = []
                all_pe_oi_surges = []
                all_ce_oi_surges = []

                for snap in snapshots:
                    result = scanner.scan_stock(snap)
                    if result.get("skipped") or "technicals" not in result:
                        logger.warning("Skipping invalid scanner result for %s", result.get("symbol", "unknown"))
                        continue
                    scanned_results.append({
                        "symbol": result["symbol"],
                        "ltp": result["technicals"]["ltp"],
                        "change_pct": result["technicals"]["change_pct"],
                        "change_pts": result["technicals"]["change_pts"],
                        "tick_change": result["tick_change"],
                        "tick_change_pct": result["tick_change_pct"],
                        "tick_timestamp": result["tick_timestamp"],
                        "momentum_direction": result["technicals"]["momentum_direction"],
                        "is_momentum_stock": result["technicals"]["is_momentum_stock"],
                        "vwap": result["technicals"]["vwap"],
                        "rsi": result["technicals"]["rsi"],
                        "ema9": result["technicals"]["ema9"],
                        "ema21": result["technicals"]["ema21"],
                        "momentum": result["technicals"]["momentum"],
                        "volume_surge": result["technicals"]["volume_surge"],
                        "oi_summary": result["oi_summary"],
                        "strikes": result["strikes"],
                        "pe_oi_surge_options": result["pe_oi_surge_options"],
                        "ce_oi_surge_options": result["ce_oi_surge_options"],
                        "strategy": result["strategy"],
                    })

                    if result["breakout_signals"]:
                        all_signals.extend(result["breakout_signals"])
                    if result["surge_strikes"]:
                        all_surges.extend(result["surge_strikes"])
                    all_pe_oi_surges.append(max(
                        result["pe_oi_surge_options"],
                        key=lambda option: option["oi_change_pct"],
                    )) if result["pe_oi_surge_options"] else None
                    all_ce_oi_surges.append(max(
                        result["ce_oi_surge_options"],
                        key=lambda option: option["oi_change_pct"],
                    )) if result["ce_oi_surge_options"] else None

                # Broadcast payload
                watchlist_stocks = [
                    stock for stock in scanned_results
                    if stock["strategy"].get("watchlist")
                ]
                high_conviction_stocks = [
                    stock for stock in watchlist_stocks
                    if stock["strategy"].get("high_conviction")
                ]
                payload = {
                    "type": "SCANNER_UPDATE",
                    "mode": active_adapter_name,
                    "is_connected": adapter.is_connected,
                    "timestamp": time.time(),
                    "stocks_count": len(scanned_results),
                    "stocks": scanned_results,
                    "watchlist_count": len(watchlist_stocks),
                    "watchlist_stocks": watchlist_stocks,
                    "high_conviction_count": len(high_conviction_stocks),
                    "high_conviction_stocks": high_conviction_stocks,
                    "breakout_signals": all_signals,
                    "surge_strikes": all_surges,
                    "pe_oi_surge_options": all_pe_oi_surges,
                    "ce_oi_surge_options": all_ce_oi_surges
                }
                await manager.broadcast(payload)
        except Exception as e:
            logger.error(f"Error in scanner broadcast loop: {e}")
            
        await asyncio.sleep(settings.SCAN_INTERVAL_MS / 1000.0)

@app.on_event("startup")
async def startup_event():
    global scanner_task
    await adapters[active_adapter_name].start()
    scanner_task = asyncio.create_task(scanner_broadcast_loop())

@app.on_event("shutdown")
async def shutdown_event():
    global scanner_task
    if scanner_task and not scanner_task.done():
        scanner_task.cancel()
        try:
            await scanner_task
        except asyncio.CancelledError:
            pass
    scanner_task = None
    for adp in adapters.values():
        await adp.stop()

# WebSocket Endpoint
@app.websocket("/ws/scanner")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Handle incoming client messages (e.g. heartbeat or filter requests)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "PING":
                    await websocket.send_json({"type": "PONG"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# REST Models & Routes
class SwitchAdapterRequest(BaseModel):
    adapter: str

class CredentialsRequest(BaseModel):
    adapter: str
    credentials: Dict[str, str]

class ThresholdsRequest(BaseModel):
    pe_surge_threshold: float
    ce_surge_threshold: float
    volume_surge_multiplier: float
    writer_proximity_pct: float

class TriggerSurgeRequest(BaseModel):
    symbol: str
    strike: float
    side: str = "PE"
    surge_pct: float = 140.0

@app.get("/api/status")
async def get_status():
    adapter = adapters.get(active_adapter_name)
    return {
        "active_adapter": active_adapter_name,
        "is_connected": adapter.is_connected if adapter else False,
        "active_clients": len(manager.active_connections),
        "thresholds": {
            "pe_surge_threshold": scanner.pe_surge_threshold,
            "ce_surge_threshold": scanner.ce_surge_threshold,
            "volume_surge_multiplier": scanner.volume_surge_multiplier,
            "writer_proximity_pct": scanner.writer_proximity_pct
        }
    }

@app.post("/api/adapter/switch")
async def switch_adapter(req: SwitchAdapterRequest):
    global active_adapter_name
    if req.adapter not in adapters:
        raise HTTPException(status_code=400, detail="Invalid adapter name")
    
    # Stop current adapter if switching
    if active_adapter_name != req.adapter:
        await adapters[active_adapter_name].stop()
        active_adapter_name = req.adapter
        await adapters[active_adapter_name].start()
        
    return {"status": "success", "active_adapter": active_adapter_name}

@app.post("/api/credentials")
async def update_credentials(req: CredentialsRequest):
    if req.adapter not in adapters:
        raise HTTPException(status_code=400, detail="Invalid adapter name")
    adapters[req.adapter].update_credentials(req.credentials)
    # Restart adapter with new credentials
    await adapters[req.adapter].start()
    return {"status": "success", "adapter": req.adapter, "is_connected": adapters[req.adapter].is_connected}

@app.post("/api/thresholds")
async def update_thresholds(req: ThresholdsRequest):
    scanner.pe_surge_threshold = req.pe_surge_threshold
    scanner.ce_surge_threshold = req.ce_surge_threshold
    scanner.volume_surge_multiplier = req.volume_surge_multiplier
    scanner.writer_proximity_pct = req.writer_proximity_pct
    return {"status": "success", "message": "Thresholds updated successfully"}

@app.get("/api/stock/{symbol}/details")
async def get_stock_details(symbol: str):
    adapter = adapters.get(active_adapter_name)
    if not adapter:
        raise HTTPException(status_code=404, detail="Adapter not found")
    
    stock_snap = adapter.get_stock_chain(symbol)
    if not stock_snap:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    analysis = scanner.scan_stock(stock_snap)
    return analysis

@app.post("/api/simulator/trigger-surge")
async def trigger_simulator_surge(req: TriggerSurgeRequest):
    if "simulator" in adapters:
        sim = adapters["simulator"]
        if isinstance(sim, MarketSimulatorAdapter):
            sim.trigger_artificial_surge(
                symbol=req.symbol,
                strike=req.strike,
                side=req.side,
                pct=req.surge_pct
            )
            return {"status": "success", "message": f"Injected {req.surge_pct}% {req.side} surge on {req.symbol} {req.strike}"}
    raise HTTPException(status_code=400, detail="Simulator not active")

# Serve Frontend static assets
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
