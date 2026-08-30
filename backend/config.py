import os
from typing import List, Dict

class Settings:
    PROJECT_NAME: str = "FnO Pulse Live Breakout & OI Scanner"
    VERSION: str = "2.0.0"
    
    # Watched FnO Universe
    DEFAULT_SYMBOLS: List[str] = [
        "NIFTY", "BANKNIFTY", "FINNIFTY",
        "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
        "SBIN", "TATAMOTORS", "TATASTEEL", "BHARTIARTL",
        "AXISBANK", "LT", "BAJFINANCE", "KOTAKBANK"
    ]
    
    # Scanner Strategy Thresholds
    PE_OI_SURGE_THRESHOLD_PCT: float = 100.0   # >= 100% change in PE OI
    CE_OI_SURGE_THRESHOLD_PCT: float = 100.0   # >= 100% change in CE OI
    VOLUME_SURGE_MULTIPLIER: float = 2.5       # Volume >= 2.5x of 20-MA
    WRITER_PROXIMITY_PCT: float = 2.0          # Call/Put seller within 2% of spot
    RSI_BULLISH_LEVEL: float = 55.0            # RSI above 55 indicates bullish strength
    RSI_BEARISH_LEVEL: float = 45.0            # RSI below 45 indicates bearish strength
    
    # Minimum OI for liquid contract filter
    MIN_OI_FILTER: int = 50000
    
    # Scanner update frequency in milliseconds
    SCAN_INTERVAL_MS: int = 1000

settings = Settings()
