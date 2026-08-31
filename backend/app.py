import asyncio
import json
import os
import hashlib
import logging
import zipfile
import requests
import traceback
from typing import List, Dict, Any, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
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
active_adapter_name = "simulator"
adapters = {
    "simulator": MarketSimulatorAdapter(),
    "fyers": FyersAdapter(),
    "kite": KiteAdapter()
}

stored_broker_credentials = {
    "fyers": {"app_id": "", "app_secret": "", "access_token": "", "redirect_uri": ""},
    "kite": {"api_key": "", "api_secret": "", "access_token": "", "redirect_uri": ""}
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

                for snap in snapshots:
                    try:
                        # Skip if snapshot has no candle history or invalid structure
                        if not snap.get("candle_history") or not snap.get("strikes"):
                            continue
                        
                        result = scanner.scan_stock(snap)
                        scanned_results.append({
                            "symbol": result["symbol"],
                            "ltp": result["technicals"]["ltp"],
                            "change_pct": result["technicals"]["change_pct"],
                            "change_pts": result["technicals"]["change_pts"],
                            "vwap": result["technicals"]["vwap"],
                            "rsi": result["technicals"]["rsi"],
                            "ema9": result["technicals"]["ema9"],
                            "ema21": result["technicals"]["ema21"],
                            "momentum": result["technicals"]["momentum"],
                            "volume_surge": result["technicals"]["volume_surge"],
                            "oi_summary": result["oi_summary"],
                        })

                        if result["breakout_signals"]:
                            all_signals.extend(result["breakout_signals"])
                        if result["surge_strikes"]:
                            all_surges.extend(result["surge_strikes"])
                    except Exception as snap_err:
                        logger.warning(f"Error scanning {snap.get('symbol', 'UNKNOWN')}: {snap_err}")
                        continue

                payload = {
                    "type": "SCANNER_UPDATE",
                    "mode": active_adapter_name,
                    "is_connected": adapter.is_connected,
                    "timestamp": asyncio.get_event_loop().time(),
                    "stocks_count": len(scanned_results),
                    "stocks": scanned_results,
                    "breakout_signals": all_signals,
                    "surge_strikes": all_surges
                }
                await manager.broadcast(payload)
        except Exception as e:
            logger.error(f"Error in scanner broadcast loop: {e}")
            logger.error(traceback.format_exc())
            
        await asyncio.sleep(settings.SCAN_INTERVAL_MS / 1000.0)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting adapters...")
    await adapters["simulator"].start()
    logger.info(f"Active adapter on startup: {active_adapter_name}")
    asyncio.create_task(scanner_broadcast_loop())

@app.on_event("shutdown")
async def shutdown_event():
    for adp in adapters.values():
        await adp.stop()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "FnO Pulse Live Scanner"}

# WebSocket Endpoint
@app.websocket("/ws/scanner")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
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

# Rest of the endpoints remain the same...
@app.get("/api/auth/fyers/login-url")
async def get_fyers_login_url(request: Request, app_id: str, app_secret: str, redirect_uri: Optional[str] = None):
    app_id = app_id.strip()
    if not app_id.endswith("-100") and "-" not in app_id and len(app_id) > 2:
        app_id = f"{app_id}-100"

    stored_broker_credentials["fyers"]["app_id"] = app_id
    stored_broker_credentials["fyers"]["app_secret"] = app_secret.strip()
    
    if not redirect_uri:
        forwarded_host = request.headers.get("x-forwarded-host", "")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            base_url = f"{forwarded_proto}://{forwarded_host}"
        else:
            base_url = str(request.base_url).rstrip("/")
            if forwarded_proto == "https" and base_url.startswith("http://"):
                base_url = "https://" + base_url[7:]
        redirect_uri = f"{base_url}/api/auth/fyers/callback"

    stored_broker_credentials["fyers"]["redirect_uri"] = redirect_uri
    auth_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={app_id}&redirect_uri={redirect_uri}&response_type=code&state=fno_pulse"
    return {"auth_url": auth_url, "redirect_uri": redirect_uri, "app_id": app_id}

@app.post("/api/auth/fyers/exchange-token")
async def manual_fyers_token_exchange(payload: Dict[str, str]):
    global active_adapter_name
    app_id = payload.get("app_id", stored_broker_credentials["fyers"]["app_id"]).strip()
    app_secret = payload.get("app_secret", stored_broker_credentials["fyers"]["app_secret"]).strip()
    auth_code_input = payload.get("auth_code", "").strip()

    if not app_id.endswith("-100") and "-" not in app_id and len(app_id) > 2:
        app_id = f"{app_id}-100"

    if "auth_code=" in auth_code_input:
        import urllib.parse
        parsed = urllib.parse.urlparse(auth_code_input)
        auth_code = urllib.parse.parse_qs(parsed.query).get("auth_code", [""])[0]
    else:
        auth_code = auth_code_input

    if not auth_code:
        raise HTTPException(status_code=400, detail="Missing auth code")

    app_id_hash = hashlib.sha256(f"{app_id}:{app_secret}".encode('utf-8')).hexdigest()
    token_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    body = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code
    }

    try:
        resp = requests.post(token_url, json=body, timeout=10)
        data = resp.json()
        access_token = data.get("access_token")
        if access_token:
            stored_broker_credentials["fyers"]["access_token"] = access_token
            await adapters["simulator"].stop()
            await adapters["kite"].stop()
            adapters["fyers"].update_credentials({"app_id": app_id, "access_token": access_token})
            await adapters["fyers"].start()
            await asyncio.sleep(0.5)
            active_adapter_name = "fyers"
            logger.info("✅ Switched to Fyers adapter")
            return {"status": "success", "access_token": access_token, "message": "Fyers connected successfully!", "adapter": "fyers"}
        else:
            raise HTTPException(status_code=400, detail=f"Fyers Token Error: {resp.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/fyers/callback")
async def fyers_oauth_callback(request: Request, auth_code: Optional[str] = None, code: Optional[str] = None):
    global active_adapter_name
    received_code = auth_code or code or request.query_params.get("auth_code") or request.query_params.get("code")
    if not received_code:
        return HTMLResponse("<h2 style='color:#FF1744;font-family:system-ui;text-align:center;padding:50px;'>❌ Error: No auth code received from Fyers.</h2>")
    
    app_id = stored_broker_credentials["fyers"]["app_id"]
    app_secret = stored_broker_credentials["fyers"]["app_secret"]
    
    if not app_id or not app_secret:
        return HTMLResponse("<h2 style='color:#FF1744;font-family:system-ui;text-align:center;padding:50px;'>❌ App ID or Secret missing. Please initiate login from the scanner settings.</h2>")
    
    app_id_hash = hashlib.sha256(f"{app_id}:{app_secret}".encode('utf-8')).hexdigest()
    token_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": received_code
    }
    
    try:
        resp = requests.post(token_url, json=payload, timeout=8)
        data = resp.json()
        access_token = data.get("access_token")
        
        if access_token:
            stored_broker_credentials["fyers"]["access_token"] = access_token
            await adapters["simulator"].stop()
            await adapters["kite"].stop()
            adapters["fyers"].update_credentials({"app_id": app_id, "access_token": access_token})
            await adapters["fyers"].start()
            await asyncio.sleep(0.5)
            active_adapter_name = "fyers"
            
            return HTMLResponse("""
            <html>
              <body style='background:#0B0E14;color:#00E676;font-family:system-ui;text-align:center;padding:60px;'>
                <h1 style='font-size:26px;'>⚡ FYERS 1-CLICK AUTHENTICATION SUCCESSFUL!</h1>
                <p style='color:#94A3B8;font-size:15px;'>Daily access token generated and connected to FnO Scanner automatically.</p>
                <div style='background:#121824;border:1px solid #1E293B;padding:15px;border-radius:10px;margin:20px auto;max-width:500px;color:#F1F5F9;word-break:break-all;font-family:monospace;font-size:12px;'>
                  """ + access_token[:35] + """... [Token Active]
                </div>
                <p style='color:#00E5FF;font-weight:bold;'>Closing this window and activating scanner...</p>
                <script>
                  if (window.opener) {
                    window.opener.postMessage({ type: 'BROKER_CONNECTED', broker: 'fyers', token: '""" + access_token + """' }, '*');
                  }
                  setTimeout(() => window.close(), 1600);
                </script>
              </body>
            </html>
            """)
        else:
            return HTMLResponse(f"<div style='background:#0B0E14;color:#FF1744;font-family:system-ui;padding:40px;text-align:center;'><h2>❌ Token Exchange Failed</h2><p style='color:#94A3B8;font-family:monospace;'>{resp.text}</p></div>")
    except Exception as e:
        return HTMLResponse(f"<div style='background:#0B0E14;color:#FF1744;font-family:system-ui;padding:40px;text-align:center;'><h2>❌ Error</h2><p>{str(e)}</p></div>")

@app.get("/api/auth/kite/login-url")
async def get_kite_login_url(request: Request, api_key: str, api_secret: str, redirect_uri: Optional[str] = None):
    stored_broker_credentials["kite"]["api_key"] = api_key.strip()
    stored_broker_credentials["kite"]["api_secret"] = api_secret.strip()
    auth_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
    return {"auth_url": auth_url}

@app.post("/api/auth/kite/exchange-token")
async def manual_kite_token_exchange(payload: Dict[str, str]):
    global active_adapter_name
    api_key = payload.get("api_key", stored_broker_credentials["kite"]["api_key"]).strip()
    api_secret = payload.get("api_secret", stored_broker_credentials["kite"]["api_secret"]).strip()
    req_token_input = payload.get("request_token", "").strip()

    if "request_token=" in req_token_input:
        import urllib.parse
        parsed = urllib.parse.urlparse(req_token_input)
        req_token = urllib.parse.parse_qs(parsed.query).get("request_token", [""])[0]
    else:
        req_token = req_token_input

    if not req_token:
        raise HTTPException(status_code=400, detail="Missing request_token")

    checksum = hashlib.sha256(f"{api_key}{req_token}{api_secret}".encode('utf-8')).hexdigest()
    token_url = "https://api.kite.trade/session/token"
    body = {
        "api_key": api_key,
        "request_token": req_token,
        "checksum": checksum
    }

    try:
        resp = requests.post(token_url, data=body, timeout=10)
        data = resp.json()
        access_token = data.get("data", {}).get("access_token")
        if access_token:
            stored_broker_credentials["kite"]["access_token"] = access_token
            await adapters["simulator"].stop()
            await adapters["fyers"].stop()
            adapters["kite"].update_credentials({"api_key": api_key, "access_token": access_token})
            await adapters["kite"].start()
            await asyncio.sleep(0.5)
            active_adapter_name = "kite"
            logger.info("✅ Switched to Kite adapter")
            return {"status": "success", "access_token": access_token, "message": "Zerodha Kite connected successfully!", "adapter": "kite"}
        else:
            raise HTTPException(status_code=400, detail=f"Kite Token Error: {resp.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/kite/callback")
async def kite_oauth_callback(request: Request, request_token: Optional[str] = None, status: Optional[str] = None):
    global active_adapter_name
    req_token = request_token or request.query_params.get("request_token")
    if not req_token:
        return HTMLResponse("<h2 style='color:#FF1744;font-family:system-ui;text-align:center;padding:50px;'>❌ Error: No request_token received from Zerodha Kite.</h2>")
    
    api_key = stored_broker_credentials["kite"]["api_key"]
    api_secret = stored_broker_credentials["kite"]["api_secret"]
    
    if not api_key or not api_secret:
        return HTMLResponse("<h2 style='color:#FF1744;font-family:system-ui;text-align:center;padding:50px;'>❌ API Key or Secret missing. Please start from Settings again.</h2>")
    
    checksum = hashlib.sha256(f"{api_key}{req_token}{api_secret}".encode('utf-8')).hexdigest()
    token_url = "https://api.kite.trade/session/token"
    payload = {
        "api_key": api_key,
        "request_token": req_token,
        "checksum": checksum
    }
    
    try:
        resp = requests.post(token_url, data=payload, timeout=8)
        data = resp.json()
        access_token = data.get("data", {}).get("access_token")
        
        if access_token:
            stored_broker_credentials["kite"]["access_token"] = access_token
            await adapters["simulator"].stop()
            await adapters["fyers"].stop()
            adapters["kite"].update_credentials({"api_key": api_key, "access_token": access_token})
            await adapters["kite"].start()
            await asyncio.sleep(0.5)
            active_adapter_name = "kite"
            
            return HTMLResponse("""
            <html>
              <body style='background:#0B0E14;color:#00E676;font-family:system-ui;text-align:center;padding:60px;'>
                <h1 style='font-size:26px;'>⚡ ZERODHA KITE 1-CLICK AUTHENTICATION SUCCESSFUL!</h1>
                <p style='color:#94A3B8;font-size:15px;'>Daily access token generated and connected to FnO Scanner automatically.</p>
                <div style='background:#121824;border:1px solid #1E293B;padding:15px;border-radius:10px;margin:20px auto;max-width:500px;color:#F1F5F9;word-break:break-all;font-family:monospace;font-size:12px;'>
                  """ + access_token[:35] + """... [Token Active]
                </div>
                <p style='color:#00E5FF;font-weight:bold;'>Closing this window and activating scanner...</p>
                <script>
                  if (window.opener) {
                    window.opener.postMessage({ type: 'BROKER_CONNECTED', broker: 'kite', token: '""" + access_token + """' }, '*');
                  }
                  setTimeout(() => window.close(), 1600);
                </script>
              </body>
            </html>
            """)
        else:
            return HTMLResponse(f"<div style='background:#0B0E14;color:#FF1744;font-family:system-ui;padding:40px;text-align:center;'><h2>❌ Token Exchange Failed</h2><p style='color:#94A3B8;font-family:monospace;'>{resp.text}</p></div>")
    except Exception as e:
        return HTMLResponse(f"<div style='background:#0B0E14;color:#FF1744;font-family:system-ui;padding:40px;text-align:center;'><h2>❌ Error</h2><p>{str(e)}</p></div>")

@app.get("/download-zip")
async def download_project_zip():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    zip_path = os.path.join(base_dir, "fno_pulse_scanner_full.zip")
    if not os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(base_dir):
                if any(x in root for x in ["__pycache__", "venv", ".git"]):
                    continue
                for file in files:
                    if not file.endswith(".zip"):
                        fpath = os.path.join(root, file)
                        zipf.write(fpath, os.path.relpath(fpath, base_dir))
    return FileResponse(zip_path, filename="fno_pulse_scanner.zip", media_type="application/zip")

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

@app.post("/api/adapter/switch")
async def switch_adapter(req: SwitchAdapterRequest):
    global active_adapter_name
    if req.adapter not in adapters:
        raise HTTPException(status_code=400, detail="Invalid adapter name")
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

# Serve Frontend static assets and index.html
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

