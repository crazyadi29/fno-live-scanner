import time
from typing import List, Dict, Any, Optional
from backend.engine.technicals import TechnicalEngine
from backend.engine.oi_analyzer import OIAnalyzer

class BreakoutScanner:
    """
    Core Scanner Engine:
    Combines Technical Momentum, Sudden Volume Surges, and Live OI Matrix
    to detect immediate high-probability breakout opportunities.
    """

    def __init__(self, pe_surge_threshold: float = 100.0, ce_surge_threshold: float = 100.0,
                 writer_proximity_pct: float = 2.5, volume_surge_multiplier: float = 2.0):
        self.pe_surge_threshold = pe_surge_threshold
        self.ce_surge_threshold = ce_surge_threshold
        self.writer_proximity_pct = writer_proximity_pct
        self.volume_surge_multiplier = volume_surge_multiplier

    def scan_stock(self, stock_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        stock_snapshot contains:
        - symbol, ltp, open, high, low, prev_close, volume, candle_history
        - strikes: list of option strikes data
        """
        symbol = stock_snapshot["symbol"]
        ltp = float(stock_snapshot["ltp"])
        if ltp <= 0:
            return {"symbol": symbol, "timestamp": int(time.time()), "skipped": True, "reason": "invalid_ltp"}
        open_p = float(stock_snapshot.get("open", ltp))
        high_p = float(stock_snapshot.get("high", ltp))
        low_p = float(stock_snapshot.get("low", ltp))
        prev_close = float(stock_snapshot.get("prev_close", ltp))
        candle_history = stock_snapshot.get("candle_history", [])
        strikes_raw = stock_snapshot.get("strikes", [])

        # 1. Technical Analysis
        technicals = TechnicalEngine.evaluate_technicals(
            symbol=symbol,
            ltp=ltp,
            open_p=open_p,
            high_p=high_p,
            low_p=low_p,
            prev_close=prev_close,
            candle_history=candle_history
        )

        # 2. OI Dynamics Analysis
        oi_analysis = OIAnalyzer.analyze_chain(
            symbol=symbol,
            spot_price=ltp,
            strikes_data=strikes_raw,
            surge_threshold_pct=self.pe_surge_threshold,
            proximity_pct=self.writer_proximity_pct
        )

        # 3. Strategy Evaluation: Bullish Breakout & Option Seller Traps
        breakout_signals = self._detect_breakouts(symbol, technicals, oi_analysis)

        return {
            "symbol": symbol,
            "timestamp": int(time.time()),
            "technicals": technicals,
            "oi_summary": {
                "total_ce_oi": oi_analysis.get("total_ce_oi", 0),
                "total_pe_oi": oi_analysis.get("total_pe_oi", 0),
                "total_ce_change": oi_analysis.get("total_ce_change", 0),
                "total_pe_change": oi_analysis.get("total_pe_change", 0),
                "pcr": oi_analysis.get("pcr", 1.0),
                "pcr_sentiment": oi_analysis.get("pcr_sentiment", "NEUTRAL"),
                "max_pain": oi_analysis.get("max_pain", ltp),
                "heavy_ce_wall": oi_analysis.get("heavy_call_writer_strike"),
                "heavy_ce_oi": oi_analysis.get("heavy_call_writer_oi", 0),
                "ce_wall_dist_pct": oi_analysis.get("ce_wall_dist_pct", 0.0),
                "heavy_pe_wall": oi_analysis.get("heavy_put_writer_strike"),
                "heavy_pe_oi": oi_analysis.get("heavy_put_writer_oi", 0),
                "pe_wall_dist_pct": oi_analysis.get("pe_wall_dist_pct", 0.0),
            },
            "surge_strikes": oi_analysis.get("surge_strikes", []),
            "breakout_signals": breakout_signals,
            "strikes": oi_analysis.get("strikes", [])
        }

    def _detect_breakouts(self, symbol: str, tech: Dict[str, Any], oi: Dict[str, Any]) -> List[Dict[str, Any]]:
        signals = []
        ltp = tech["ltp"]
        is_bullish_momentum = tech["momentum"] in ["BULLISH_BREAKOUT", "BULLISH_STRONG", "BULLISH_MILD"]
        ce_wall = oi.get("heavy_call_writer_strike")
        ce_wall_dist = oi.get("ce_wall_dist_pct", 999.0)
        pe_wall = oi.get("heavy_put_writer_strike")
        pe_wall_dist = oi.get("pe_wall_dist_pct", 999.0)

        # Check for individual surge strikes
        for s in oi.get("surge_strikes", []):
            strike = s["strike"]
            pe_chg_pct = s["pe_change_pct"]
            ce_chg_pct = s["ce_change_pct"]
            is_nearby = s["is_nearby"]
            
            # --- STRATEGY 1: Bullish Momentum + Heavy CE Wall Nearby + PE OI Surge > 100% ---
            if is_bullish_momentum and pe_chg_pct >= self.pe_surge_threshold and is_nearby:
                # Find the target CE option contract to trade
                target_ce_strike = ce_wall if (ce_wall and ltp > 0 and abs(ce_wall - ltp)/ltp <= 0.03) else strike
                
                # Fetch target strike LTP
                target_ltp = 0.0
                for st in oi.get("strikes", []):
                    if st["strike"] == target_ce_strike:
                        target_ltp = st["ce_ltp"]
                        break

                confidence = 85
                if tech["volume_surge"]["is_surge"]: confidence += 10
                if tech["is_near_day_high"]: confidence += 5
                confidence = min(98, confidence)

                signals.append({
                    "id": f"SIG_{symbol}_{strike}_{int(time.time())}",
                    "symbol": symbol,
                    "type": "BULLISH_RESISTANCE_SQUEEZE",
                    "action": "BUY_CALL",
                    "recommended_option": f"{symbol} {int(target_ce_strike)} CE",
                    "option_strike": target_ce_strike,
                    "option_type": "CE",
                    "option_ltp": target_ltp,
                    "spot_ltp": ltp,
                    "pe_oi_surge_pct": pe_chg_pct,
                    "ce_writer_wall": ce_wall,
                    "ce_wall_dist_pct": ce_wall_dist,
                    "confidence": confidence,
                    "headline": f"🔥 {symbol} {int(strike)} PE Writing Surge (+{pe_chg_pct}%)",
                    "reason": f"Bullish momentum with aggressive Put Writing (+{pe_chg_pct}% PE OI). Stock approaching Call Seller Wall at {ce_wall} ({ce_wall_dist}% away). High probability of Resistance Breakout / Short Squeeze!",
                    "timestamp": int(time.time()),
                    "priority": "HIGH"
                })

            # --- STRATEGY 2: Bearish Breakdown + Heavy PE Wall Nearby + CE OI Surge > 100% ---
            elif (not is_bullish_momentum) and ce_chg_pct >= self.ce_surge_threshold and is_nearby:
                target_pe_strike = pe_wall if (pe_wall and ltp > 0 and abs(pe_wall - ltp)/ltp <= 0.03) else strike
                target_ltp = 0.0
                for st in oi.get("strikes", []):
                    if st["strike"] == target_pe_strike:
                        target_ltp = st["pe_ltp"]
                        break

                signals.append({
                    "id": f"SIG_BEAR_{symbol}_{strike}_{int(time.time())}",
                    "symbol": symbol,
                    "type": "BEARISH_SUPPORT_BREAKDOWN",
                    "action": "BUY_PUT",
                    "recommended_option": f"{symbol} {int(target_pe_strike)} PE",
                    "option_strike": target_pe_strike,
                    "option_type": "PE",
                    "option_ltp": target_ltp,
                    "spot_ltp": ltp,
                    "ce_oi_surge_pct": ce_chg_pct,
                    "pe_writer_wall": pe_wall,
                    "pe_wall_dist_pct": pe_wall_dist,
                    "confidence": 80,
                    "headline": f"⚠️ {symbol} {int(strike)} CE Writing Surge (+{ce_chg_pct}%)",
                    "reason": f"Aggressive Call Writing (+{ce_chg_pct}% CE OI) suffocating price near Put Support at {pe_wall}. Support Breakdown imminent!",
                    "timestamp": int(time.time()),
                    "priority": "MEDIUM"
                })

        return signals
