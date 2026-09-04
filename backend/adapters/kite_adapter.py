import asyncio
import requests
import json
import logging
from typing import List, Dict, Any, Optional
from backend.adapters.base import BaseBrokerAdapter

logger = logging.getLogger(__name__)

class KiteAdapter(BaseBrokerAdapter):
    """
    Zerodha Kite Connect Integration Adapter.
    Handles REST authentication, Option Chain queries, and LTP updates.
    """
    BASE_URL = "https://api.kite.trade"

    def __init__(self, api_key: str = "", access_token: str = ""):
        super().__init__("Kite")
        self.api_key = api_key
        self.access_token = access_token
        self._running = False
        self._cache: Dict[str, Dict[str, Any]] = {}

    def update_credentials(self, credentials: Dict[str, str]):
        super().update_credentials(credentials)
        self.api_key = credentials.get("api_key", self.api_key)
        self.access_token = credentials.get("access_token", self.access_token)
        self.is_connected = bool(self.api_key and self.access_token)

    async def start(self):
        self._running = True
        if self.api_key and self.access_token:
            self.is_connected = True
            asyncio.create_task(self._poll_loop())
        else:
            self.is_connected = False

    async def stop(self):
        self._running = False
        self.is_connected = False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

    async def fetch_quotes(self, instruments: List[str]) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        url = f"{self.BASE_URL}/quote"
        params = [("i", inst) for inst in instruments]
        try:
            resp = requests.get(url, headers=self._get_headers(), params=params, timeout=4)
            if resp.status_code == 200:
                return resp.json().get("data", {})
        except Exception as e:
            logger.error(f"Kite API fetch error: {e}")
        return None

    async def _poll_loop(self):
        while self._running and self.is_connected:
            # Polling cycle
            await asyncio.sleep(1.0)

    def get_market_snapshots(self) -> List[Dict[str, Any]]:
        return list(self._cache.values())

    def get_stock_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(symbol)
