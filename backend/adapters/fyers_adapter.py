import asyncio
import requests
import json
import logging
from typing import List, Dict, Any, Optional
from backend.adapters.base import BaseBrokerAdapter

logger = logging.getLogger(__name__)

class FyersAdapter(BaseBrokerAdapter):
    """
    Fyers API v3 Integration Adapter.
    Handles REST authentication, Option Chain endpoint queries,
    and live WebSocket feed updates.
    """
    BASE_URL = "https://api-t1.fyers.in/data"

    def __init__(self, app_id: str = "", access_token: str = ""):
        super().__init__("Fyers")
        self.app_id = app_id
        self.access_token = access_token
        self._running = False
        self._cache: Dict[str, Dict[str, Any]] = {}

    def update_credentials(self, credentials: Dict[str, str]):
        super().update_credentials(credentials)
        self.app_id = credentials.get("app_id", self.app_id)
        self.access_token = credentials.get("access_token", self.access_token)
        self.is_connected = bool(self.app_id and self.access_token)

    async def start(self):
        self._running = True
        if self.app_id and self.access_token:
            self.is_connected = True
            asyncio.create_task(self._poll_loop())
        else:
            self.is_connected = False

    async def stop(self):
        self._running = False
        self.is_connected = False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"{self.app_id}:{self.access_token}",
            "Content-Type": "application/json"
        }

    async def fetch_option_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Calls Fyers v3 Option Chain API:
        GET /data/options-chain-v3?symbol=NSE:{symbol}-INDEX or NSE:{symbol}-EQ
        """
        if not self.is_connected:
            return None

        # Format symbol for Fyers
        fyers_sym = f"NSE:{symbol}-INDEX" if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"] else f"NSE:{symbol}-EQ"
        url = f"{self.BASE_URL}/options-chain-v3"
        params = {"symbol": fyers_sym, "strikecount": 15}

        try:
            resp = requests.get(url, headers=self._get_headers(), params=params, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_fyers_chain(symbol, data)
            else:
                logger.error(f"Fyers API HTTP {resp.status_code} for {symbol}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Fyers API fetch error for {symbol}: {e}")
        return None

    def _parse_fyers_chain(self, symbol: str, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Translates Fyers API JSON format into uniform scanner format"""
        chain_data = raw_data.get("data", {}).get("optionsChain", [])
        spot = raw_data.get("data", {}).get("spotPrice", 0.0)

        if not spot or spot <= 0:
            logger.warning(f"Skipping {symbol}: invalid spotPrice={spot!r} in Fyers response")
            return None

        strikes = []
        for item in chain_data:
            strike_val = item.get("strike_price", 0.0)
            ce = item.get("call_opt", {})
            pe = item.get("put_opt", {})

            strikes.append({
                "strike": strike_val,
                "ce_oi": ce.get("oi", 0),
                "ce_change_oi": ce.get("oich", 0),
                "ce_ltp": ce.get("ltp", 0.0),
                "ce_volume": ce.get("volume", 0),
                "pe_oi": pe.get("oi", 0),
                "pe_change_oi": pe.get("oich", 0),
                "pe_ltp": pe.get("ltp", 0.0),
                "pe_volume": pe.get("volume", 0)
            })

        return {
            "symbol": symbol,
            "ltp": spot,
            "open": raw_data.get("data", {}).get("open", spot),
            "high": raw_data.get("data", {}).get("high", spot),
            "low": raw_data.get("data", {}).get("low", spot),
            "prev_close": raw_data.get("data", {}).get("prev_close", spot),
            "strikes": strikes
        }

    async def _poll_loop(self):
        symbols = ["NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN"]
        while self._running and self.is_connected:
            for sym in symbols:
                try:
                    res = await self.fetch_option_chain(sym)
                    if res:
                        self._cache[sym] = res
                except Exception:
                    pass
                await asyncio.sleep(0.2)
            await asyncio.sleep(1.0)

    def get_market_snapshots(self) -> List[Dict[str, Any]]:
        return list(self._cache.values())

    def get_stock_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(symbol)
