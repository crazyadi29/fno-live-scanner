import asyncio
import csv
import io
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from backend.adapters.base import BaseBrokerAdapter
from backend.config import settings

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
        self._poll_task: Optional[asyncio.Task] = None

    def update_credentials(self, credentials: Dict[str, str]):
        super().update_credentials(credentials)
        self.app_id = credentials.get("app_id", self.app_id)
        self.access_token = credentials.get("access_token", self.access_token)
        self.is_connected = bool(self.app_id and self.access_token)

    async def start(self):
        await self.stop()
        self._running = True
        if self.app_id and self.access_token:
            self.is_connected = True
            self._poll_task = asyncio.create_task(self._poll_loop())
        else:
            self.is_connected = False

    async def stop(self):
        self._running = False
        self.is_connected = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None

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
            resp = await asyncio.to_thread(
                requests.get, url, headers=self._get_headers(), params=params, timeout=4
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("s") != "ok":
                    logger.error(
                        "Fyers API response error for %s: status=%r code=%r message=%r",
                        symbol, data.get("s"), data.get("code"), data.get("message")
                    )
                    return None
                response_data = data.get("data") or {}
                if not response_data.get("spotPrice"):
                    quote_price = await self.fetch_spot_price(fyers_sym)
                    if quote_price:
                        response_data["spotPrice"] = quote_price
                candles = await self.fetch_5m_history(fyers_sym)
                if candles:
                    response_data["candle_history"] = candles
                    response_data["candle_timeframe"] = "5m"
                return self._parse_fyers_chain(symbol, data)
            else:
                logger.error(f"Fyers API HTTP {resp.status_code} for {symbol}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Fyers API fetch error for {symbol}: {e}")
        return None

    async def fetch_spot_price(self, fyers_symbol: str) -> Optional[float]:
        """Get the underlying LTP when the option-chain response omits it."""
        try:
            response = await asyncio.to_thread(
                requests.get,
                f"{self.BASE_URL}/quotes",
                headers=self._get_headers(),
                params={"symbols": fyers_symbol},
                timeout=4,
            )
            if response.status_code != 200:
                return None
            data = response.json()
            quote = (data.get("d") or [{}])[0]
            price = (quote.get("v") or {}).get("lp")
            return float(price) if price else None
        except (requests.RequestException, ValueError, TypeError, IndexError):
            return None

    async def fetch_5m_history(self, fyers_symbol: str) -> List[Dict[str, float]]:
        """Fetch recent 5-minute candles for chart-based support and resistance."""
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=5)
        params = {
            "symbol": fyers_symbol,
            "resolution": "5",
            "date_format": "1",
            "range_from": start.isoformat(),
            "range_to": today.isoformat(),
            "cont_flag": "1",
        }
        try:
            response = await asyncio.to_thread(
                requests.get,
                f"{self.BASE_URL}/history",
                headers=self._get_headers(),
                params=params,
                timeout=6,
            )
            if response.status_code != 200:
                return []
            data = response.json()
            if data.get("s") != "ok":
                return []
            return [
                {
                    "timestamp": float(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                }
                for candle in data.get("candles", [])
                if len(candle) >= 6
            ]
        except (requests.RequestException, ValueError, TypeError, IndexError):
            return []

    def _parse_fyers_chain(self, symbol: str, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Translates Fyers API JSON format into uniform scanner format"""
        response_data = raw_data.get("data") or {}
        chain_data = response_data.get("optionsChain", [])
        spot = response_data.get("spotPrice", 0.0)

        if not spot or spot <= 0:
            logger.warning(
                "Skipping %s: invalid spotPrice=%r, api_status=%r, code=%r, message=%r",
                symbol, spot, raw_data.get("s"), raw_data.get("code"), raw_data.get("message")
            )
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
            "candle_history": response_data.get("candle_history", []),
            "candle_timeframe": response_data.get("candle_timeframe", "unknown"),
            "strikes": strikes
        }

    async def _poll_loop(self):
        symbols = await self._load_fno_universe()
        logger.info("Scanning %d F&O underlyings", len(symbols))
        while self._running and self.is_connected:
            for sym in symbols:
                if not self._running or not self.is_connected:
                    break
                try:
                    res = await self.fetch_option_chain(sym)
                    if res:
                        self._cache[sym] = res
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("Fyers polling error for %s: %s", sym, exc)
                await asyncio.sleep(0.2)
            await asyncio.sleep(max(1.0, settings.SCAN_INTERVAL_MS / 1000.0))

    async def _load_fno_universe(self) -> List[str]:
        """Load unique F&O underlyings from the daily Fyers symbol master."""
        url = "https://public.fyers.in/sym_details/NSE_FO.csv"
        try:
            response = await asyncio.to_thread(requests.get, url, timeout=15)
            response.raise_for_status()
            symbols = set()
            for row in csv.reader(io.StringIO(response.text)):
                if len(row) <= 13:
                    continue
                trading_symbol = row[9]
                underlying = row[13].strip()
                if underlying and trading_symbol.startswith("NSE:") and trading_symbol.endswith(("FUT", "CE", "PE")):
                    symbols.add(underlying)
            if symbols:
                return sorted(symbols)
            logger.warning("Fyers symbol master returned no F&O underlyings")
        except (requests.RequestException, csv.Error) as exc:
            logger.warning("Unable to load Fyers F&O universe: %s", exc)
        return settings.DEFAULT_SYMBOLS

    def get_market_snapshots(self) -> List[Dict[str, Any]]:
        return list(self._cache.values())

    def get_stock_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(symbol)
