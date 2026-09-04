from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseBrokerAdapter(ABC):
    """
    Abstract interface for market data connectors (Simulator, Fyers, Kite)
    """
    def __init__(self, name: str):
        self.name = name
        self.is_connected = False
        self.credentials: Dict[str, str] = {}

    @abstractmethod
    async def start(self):
        """Initialize connections, websockets, background polling"""
        pass

    @abstractmethod
    async def stop(self):
        """Cleanup connections"""
        pass

    @abstractmethod
    def get_market_snapshots(self) -> List[Dict[str, Any]]:
        """Returns current full market snapshot for all tracked FnO stocks"""
        pass

    @abstractmethod
    def get_stock_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Returns option chain and details for a single symbol"""
        pass

    def update_credentials(self, credentials: Dict[str, str]):
        self.credentials.update(credentials)
