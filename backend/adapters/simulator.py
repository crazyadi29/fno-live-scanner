import asyncio
import random
import math
import time
from typing import List, Dict, Any, Optional
from backend.adapters.base import BaseBrokerAdapter

class MarketSimulatorAdapter(BaseBrokerAdapter):
    """
    High-fidelity NSE FnO Market Simulator.
    Generates live ticks, order flow volume bursts, realistic option chains,
    and simulated >100% PE/CE OI surges for real-time scanner testing.
    """

    STOCK_CONFIG = {
        "NIFTY": {"base": 24850.0, "step": 50, "lot": 50, "volatility": 0.0008},
        "BANKNIFTY": {"base": 53200.0, "step": 100, "lot": 15, "volatility": 0.0012},
        "FINNIFTY": {"base": 23900.0, "step": 50, "lot": 40, "volatility": 0.0010},
        "RELIANCE": {"base": 3015.0, "step": 20, "lot": 250, "volatility": 0.0015},
        "HDFCBANK": {"base": 1685.0, "step": 10, "lot": 550, "volatility": 0.0013},
        "ICICIBANK": {"base": 1245.0, "step": 10, "lot": 700, "volatility": 0.0014},
        "INFY": {"base": 1865.0, "step": 20, "lot": 400, "volatility": 0.0016},
        "TCS": {"base": 4350.0, "step": 50, "lot": 175, "volatility": 0.0011},
        "SBIN": {"base": 842.0, "step": 5, "lot": 1500, "volatility": 0.0017},
        "TATAMOTORS": {"base": 1085.0, "step": 10, "lot": 575, "volatility": 0.0020},
        "TATASTEEL": {"base": 174.5, "step": 2.5, "lot": 5500, "volatility": 0.0019},
        "BHARTIARTL": {"base": 1560.0, "step": 10, "lot": 475, "volatility": 0.0014},
        "AXISBANK": {"base": 1220.0, "step": 10, "lot": 625, "volatility": 0.0015},
        "LT": {"base": 3680.0, "step": 20, "lot": 150, "volatility": 0.0013},
        "BAJFINANCE": {"base": 7250.0, "step": 50, "lot": 125, "volatility": 0.0018},
        "KOTAKBANK": {"base": 1825.0, "step": 10, "lot": 400, "volatility": 0.0012},
    }

    def __init__(self):
        super().__init__("Simulator")
        self._running = False
        self._stocks: Dict[str, Dict[str, Any]] = {}
        self._initialize_universe()

    def _initialize_universe(self):
        for sym, cfg in self.STOCK_CONFIG.items():
            base_p = cfg["base"]
            step = cfg["step"]
            open_p = round(base_p * (1.0 + random.uniform(-0.004, 0.004)), 2)
            prev_close = base_p
            high_p = max(open_p, round(open_p * (1.0 + random.uniform(0.002, 0.015)), 2))
            low_p = min(open_p, round(open_p * (1.0 - random.uniform(0.002, 0.008)), 2))
            ltp = round(open_p * (1.0 + random.uniform(0.003, 0.012)), 2)
            high_p = max(high_p, ltp)
            low_p = min(low_p, ltp)

            # Generate initial candle history (20 candles)
            candles = []
            c_price = open_p
            for i in range(20):
                c_high = round(c_price * (1.0 + random.uniform(0.0005, 0.002)), 2)
                c_low = round(c_price * (1.0 - random.uniform(0.0005, 0.002)), 2)
                c_close = round(random.uniform(c_low, c_high), 2)
                c_vol = random.randint(10000, 50000)
                candles.append({"high": c_high, "low": c_low, "close": c_close, "volume": c_vol})
                c_price = c_close

            # Generate Option Strikes ladder (+- 10 strikes)
            strikes = []
            center_strike = round(ltp / step) * step
            for i in range(-10, 11):
                s_val = round(center_strike + i * step, 2)
                
                # Base OI distribution (Heavy CE higher up, heavy PE lower down)
                dist_factor = abs(s_val - ltp) / (step * 5)
                base_oi = int(max(15000, 120000 / (1.0 + dist_factor))) * cfg["lot"]
                
                # Call Option
                ce_intrinsic = max(0.0, ltp - s_val)
                ce_time_val = max(1.5, step * 0.8 * math.exp(-abs(s_val - ltp) / (step * 3)))
                ce_ltp = round(ce_intrinsic + ce_time_val, 2)
                ce_oi = int(base_oi * random.uniform(0.8, 1.3))
                ce_chg = int(ce_oi * random.uniform(-0.15, 0.35))
                ce_vol = int(ce_oi * random.uniform(0.1, 0.4))

                # Put Option
                pe_intrinsic = max(0.0, s_val - ltp)
                pe_time_val = max(1.5, step * 0.8 * math.exp(-abs(s_val - ltp) / (step * 3)))
                pe_ltp = round(pe_intrinsic + pe_time_val, 2)
                pe_oi = int(base_oi * random.uniform(0.8, 1.3))
                pe_chg = int(pe_oi * random.uniform(-0.15, 0.35))
                pe_vol = int(pe_oi * random.uniform(0.1, 0.4))

                strikes.append({
                    "strike": s_val,
                    "ce_oi": ce_oi,
                    "ce_change_oi": ce_chg,
                    "ce_ltp": ce_ltp,
                    "ce_volume": ce_vol,
                    "pe_oi": pe_oi,
                    "pe_change_oi": pe_chg,
                    "pe_ltp": pe_ltp,
                    "pe_volume": pe_vol
                })

            self._stocks[sym] = {
                "symbol": sym,
                "ltp": ltp,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "prev_close": prev_close,
                "step": step,
                "lot": cfg["lot"],
                "volatility": cfg["volatility"],
                "candle_history": candles,
                "strikes": strikes,
                "last_surge_time": 0
            }

        # Seed initial surge for RELIANCE and NIFTY to demonstrate live breakout capability right away
        self._inject_surge("RELIANCE", side="PE", pct_boost=145.0)
        self._inject_surge("NIFTY", side="PE", pct_boost=125.0)

    def _inject_surge(self, symbol: str, side: str = "PE", pct_boost: float = 120.0, strike_val: Optional[float] = None):
        if symbol not in self._stocks:
            return
        stock = self._stocks[symbol]
        ltp = stock["ltp"]
        step = stock["step"]
        
        # Pick ATM or nearest OTM strike
        target_strike = strike_val
        if target_strike is None:
            if side == "PE":
                target_strike = round(ltp / step) * step  # ATM strike
            else:
                target_strike = (round(ltp / step) + 1) * step # Near OTM Call

        for s in stock["strikes"]:
            if abs(s["strike"] - target_strike) < (step * 0.5):
                if side == "PE":
                    prev_oi = max(20000, s["pe_oi"] - s["pe_change_oi"])
                    new_chg = int(prev_oi * (pct_boost / 100.0))
                    s["pe_change_oi"] = new_chg
                    s["pe_oi"] = prev_oi + new_chg
                    s["pe_volume"] = int(s["pe_volume"] * 3.5)
                else:
                    prev_oi = max(20000, s["ce_oi"] - s["ce_change_oi"])
                    new_chg = int(prev_oi * (pct_boost / 100.0))
                    s["ce_change_oi"] = new_chg
                    s["ce_oi"] = prev_oi + new_chg
                    s["ce_volume"] = int(s["ce_volume"] * 3.5)
                break

    async def start(self):
        self._running = True
        self.is_connected = True
        asyncio.create_task(self._simulation_loop())

    async def stop(self):
        self._running = False
        self.is_connected = False

    async def _simulation_loop(self):
        step_counter = 0
        while self._running:
            try:
                step_counter += 1
                for sym, stock in self._stocks.items():
                    # 1. Update spot price with random walk + slight upward bias for bullish stocks
                    vol = stock["volatility"]
                    drift = 0.0001 if sym in ["RELIANCE", "NIFTY", "HDFCBANK", "ICICIBANK", "SBIN"] else -0.00005
                    shock = random.gauss(drift, vol)
                    new_ltp = round(stock["ltp"] * (1.0 + shock), 2)
                    
                    stock["ltp"] = new_ltp
                    stock["high"] = max(stock["high"], new_ltp)
                    stock["low"] = min(stock["low"], new_ltp)

                    # 2. Update current candle
                    if stock["candle_history"]:
                        curr_c = stock["candle_history"][-1]
                        curr_c["high"] = max(curr_c["high"], new_ltp)
                        curr_c["low"] = min(curr_c["low"], new_ltp)
                        curr_c["close"] = new_ltp
                        curr_c["volume"] += random.randint(50, 400)

                    # 3. Dynamic Option Chain Tick
                    step = stock["step"]
                    for s in stock["strikes"]:
                        s_val = s["strike"]
                        # Call price dynamic
                        ce_intrinsic = max(0.0, new_ltp - s_val)
                        ce_time_val = max(1.5, step * 0.8 * math.exp(-abs(s_val - new_ltp) / (step * 3)))
                        s["ce_ltp"] = round(ce_intrinsic + ce_time_val, 2)
                        
                        # Put price dynamic
                        pe_intrinsic = max(0.0, s_val - new_ltp)
                        pe_time_val = max(1.5, step * 0.8 * math.exp(-abs(s_val - new_ltp) / (step * 3)))
                        s["pe_ltp"] = round(pe_intrinsic + pe_time_val, 2)

                        # Small incremental OI changes on active strikes
                        if random.random() < 0.25:
                            s["ce_oi"] += random.randint(-50, 150) * stock["lot"]
                            s["pe_oi"] += random.randint(-50, 200) * stock["lot"]

                # 4. Periodically inject random surges (every ~20 seconds on rotating stocks)
                if step_counter % 20 == 0:
                    random_sym = random.choice(["HDFCBANK", "TATAMOTORS", "TCS", "INFY", "BHARTIARTL", "SBIN"])
                    surge_side = "PE" if random.random() < 0.75 else "CE"
                    boost = random.uniform(105.0, 185.0)
                    self._inject_surge(random_sym, side=surge_side, pct_boost=boost)

                await asyncio.sleep(1.0)
            except Exception as e:
                await asyncio.sleep(1.0)

    def trigger_artificial_surge(self, symbol: str, strike: float, side: str = "PE", pct: float = 135.0):
        """User-triggered instant surge for testing & verification"""
        self._inject_surge(symbol, side=side, pct_boost=pct, strike_val=strike)

    def get_market_snapshots(self) -> List[Dict[str, Any]]:
        return list(self._stocks.values())

    def get_stock_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._stocks.get(symbol)
