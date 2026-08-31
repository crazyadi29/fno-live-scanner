import math
from typing import List, Dict, Any, Optional

class TechnicalEngine:
    """
    Computes real-time technical indicators for FnO stocks:
    - VWAP (Volume Weighted Average Price)
    - EMA (9 & 21)
    - RSI (14)
    - Volume Surge Ratio (Current Vol vs 20-period Moving Average)
    - Day High/Low Breakout Proximity
    - Bullish / Bearish Momentum Classification
    """

    @staticmethod
    def calculate_vwap(candles: List[Dict[str, float]]) -> float:
        """
        candles: list of dicts with 'high', 'low', 'close', 'volume'
        """
        if not candles:
            return 0.0
        cum_pv = sum(((c['high'] + c['low'] + c['close']) / 3.0) * c['volume'] for c in candles)
        cum_vol = sum(c['volume'] for c in candles)
        return round(cum_pv / cum_vol, 2) if cum_vol > 0 else candles[-1]['close']

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        if not prices:
            return 0.0
        if len(prices) < period:
            return prices[-1]
        
        multiplier = 2.0 / (period + 1.0)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 2)

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        if len(prices) <= period:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(rsi, 2)

    @staticmethod
    def calculate_volume_surge(volumes: List[float], window: int = 20) -> Dict[str, Any]:
        """
        Returns volume surge multiplier = current_volume / avg_volume
        """
        if not volumes:
            return {"surge_ratio": 1.0, "is_surge": False, "avg_vol": 0, "curr_vol": 0}
        
        curr_vol = volumes[-1]
        hist_vols = volumes[-window:-1] if len(volumes) > 1 else [curr_vol]
        avg_vol = sum(hist_vols) / len(hist_vols) if hist_vols else curr_vol
        
        if avg_vol <= 0:
            avg_vol = max(1.0, curr_vol)
            
        ratio = round(curr_vol / avg_vol, 2)
        return {
            "surge_ratio": ratio,
            "is_surge": ratio >= 2.0,
            "avg_vol": int(avg_vol),
            "curr_vol": int(curr_vol)
        }

    @staticmethod
    def evaluate_technicals(symbol: str, ltp: float, open_p: float, high_p: float, low_p: float,
                            prev_close: float, candle_history: List[Dict[str, float]]) -> Dict[str, Any]:
        closes = [c['close'] for c in candle_history] if candle_history else [ltp]
        volumes = [c['volume'] for c in candle_history] if candle_history else [1000]
        
        if not closes or closes[-1] != ltp:
            closes.append(ltp)
            
        vwap = TechnicalEngine.calculate_vwap(candle_history) if candle_history else round((high_p + low_p + ltp) / 3, 2)
        ema9 = TechnicalEngine.calculate_ema(closes, 9)
        ema21 = TechnicalEngine.calculate_ema(closes, 21)
        rsi = TechnicalEngine.calculate_rsi(closes, 14)
        vol_surge = TechnicalEngine.calculate_volume_surge(volumes, 20)
        
        change_pts = round(ltp - prev_close, 2)
        change_pct = round((change_pts / prev_close) * 100.0, 2) if prev_close > 0 else 0.0
        
        # Day Range & Breakout Proximity
        day_range = max(0.01, high_p - low_p)
        pos_in_range = round(((ltp - low_p) / day_range) * 100.0, 1) if ltp > 0 else 0.0
        dist_to_high_pct = round(((high_p - ltp) / ltp) * 100.0, 2) if ltp > 0 else 0.0
        is_near_day_high = dist_to_high_pct <= 0.4 if ltp > 0 else False
        
        # Trend and Momentum Evaluation
        is_above_vwap = ltp >= vwap
        is_ema_bullish = ema9 > ema21
        is_rsi_bullish = rsi >= 55.0
        is_rsi_bearish = rsi <= 45.0
        
        bullish_score = 0
        if is_above_vwap: bullish_score += 1
        if is_ema_bullish: bullish_score += 1
        if is_rsi_bullish: bullish_score += 1
        if change_pct > 0.5: bullish_score += 1
        if is_near_day_high: bullish_score += 1
        if vol_surge["is_surge"]: bullish_score += 1
        
        if bullish_score >= 4:
            momentum = "BULLISH_BREAKOUT" if is_near_day_high and vol_surge["is_surge"] else "BULLISH_STRONG"
            signal_color = "#00E676" # Bright Green
        elif bullish_score >= 3:
            momentum = "BULLISH_MILD"
            signal_color = "#69F0AE"
        elif rsi <= 42 and ltp < vwap and change_pct < -0.5:
            momentum = "BEARISH_BREAKDOWN" if (ltp - low_p)/ltp < 0.004 and vol_surge["is_surge"] else "BEARISH_STRONG"
            signal_color = "#FF1744" # Bright Red
        else:
            momentum = "NEUTRAL"
            signal_color = "#B0BEC5" # Grey
            
        return {
            "symbol": symbol,
            "ltp": ltp,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "prev_close": prev_close,
            "change_pts": change_pts,
            "change_pct": change_pct,
            "vwap": vwap,
            "ema9": ema9,
            "ema21": ema21,
            "rsi": rsi,
            "volume_surge": vol_surge,
            "dist_to_high_pct": dist_to_high_pct,
            "pos_in_range_pct": pos_in_range,
            "is_near_day_high": is_near_day_high,
            "is_above_vwap": is_above_vwap,
            "momentum": momentum,
            "momentum_score": bullish_score,
            "signal_color": signal_color
        }

