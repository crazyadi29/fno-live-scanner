from typing import List, Dict, Any, Optional

class OIAnalyzer:
    """
    Analyzes Open Interest (OI) dynamics, Put-Call Ratios,
    Writer Concentration Zones (Support & Resistance walls),
    and detects sudden surges in PE OI / CE OI (>100% change).
    """

    @staticmethod
    def analyze_chain(symbol: str, spot_price: float, strikes_data: List[Dict[str, Any]],
                      surge_threshold_pct: float = 100.0,
                      proximity_pct: float = 2.5) -> Dict[str, Any]:
        """
        strikes_data item structure:
        {
            "strike": float,
            "ce_oi": int,
            "ce_change_oi": int,
            "ce_ltp": float,
            "ce_volume": int,
            "pe_oi": int,
            "pe_change_oi": int,
            "pe_ltp": float,
            "pe_volume": int
        }
        """
        if not strikes_data or not spot_price or spot_price <= 0:
            return {}

        total_ce_oi = 0
        total_pe_oi = 0
        total_ce_change = 0
        total_pe_change = 0
        
        max_ce_oi = -1
        max_ce_strike = None
        max_pe_oi = -1
        max_pe_strike = None
        
        surge_strikes = []
        pe_oi_surge_options = []
        ce_oi_surge_options = []
        processed_strikes = []

        for row in strikes_data:
            strike = row["strike"]
            ce_oi = int(row.get("ce_oi", 0))
            ce_chg = int(row.get("ce_change_oi", 0))
            ce_ltp = float(row.get("ce_ltp", 0.0))
            ce_vol = int(row.get("ce_volume", 0))

            pe_oi = int(row.get("pe_oi", 0))
            pe_chg = int(row.get("pe_change_oi", 0))
            pe_ltp = float(row.get("pe_ltp", 0.0))
            pe_vol = int(row.get("pe_volume", 0))

            # Prev OI base
            prev_ce_oi = max(1, ce_oi - ce_chg)
            prev_pe_oi = max(1, pe_oi - pe_chg)

            ce_chg_pct = round((ce_chg / prev_ce_oi) * 100.0, 1)
            pe_chg_pct = round((pe_chg / prev_pe_oi) * 100.0, 1)

            total_ce_oi += ce_oi
            total_pe_oi += pe_oi
            total_ce_change += ce_chg
            total_pe_change += pe_chg

            # Distance from spot
            dist_pts = round(strike - spot_price, 2)
            dist_pct = round((abs(dist_pts) / spot_price) * 100.0, 2)
            is_nearby = dist_pct <= proximity_pct

            # Track heavy writer zones
            if ce_oi > max_ce_oi and strike >= spot_price * 0.98:
                max_ce_oi = ce_oi
                max_ce_strike = strike

            if pe_oi > max_pe_oi and strike <= spot_price * 1.02:
                max_pe_oi = pe_oi
                max_pe_strike = strike

            # Check for sudden surges (> 100% change in OI)
            has_pe_surge = pe_chg_pct >= surge_threshold_pct
            has_ce_surge = ce_chg_pct >= surge_threshold_pct

            surge_type = None
            if has_pe_surge and has_ce_surge:
                surge_type = "BOTH_SURGE"
            elif has_pe_surge:
                surge_type = "PE_OI_SURGE"
            elif has_ce_surge:
                surge_type = "CE_OI_SURGE"

            strike_info = {
                "strike": strike,
                "dist_pts": dist_pts,
                "dist_pct": dist_pct,
                "is_nearby": is_nearby,
                "ce_oi": ce_oi,
                "ce_change_oi": ce_chg,
                "ce_change_pct": ce_chg_pct,
                "ce_ltp": ce_ltp,
                "ce_volume": ce_vol,
                "pe_oi": pe_oi,
                "pe_change_oi": pe_chg,
                "pe_change_pct": pe_chg_pct,
                "pe_ltp": pe_ltp,
                "pe_volume": pe_vol,
                "surge_type": surge_type
            }
            processed_strikes.append(strike_info)

            if has_pe_surge:
                pe_oi_surge_options.append({
                    "symbol": symbol, "strike": strike, "option_type": "PE",
                    "oi": pe_oi, "oi_change": pe_chg, "oi_change_pct": pe_chg_pct,
                    "ltp": pe_ltp, "volume": pe_vol, "dist_pct": dist_pct,
                })
            if has_ce_surge:
                ce_oi_surge_options.append({
                    "symbol": symbol, "strike": strike, "option_type": "CE",
                    "oi": ce_oi, "oi_change": ce_chg, "oi_change_pct": ce_chg_pct,
                    "ltp": ce_ltp, "volume": ce_vol, "dist_pct": dist_pct,
                })

            if surge_type is not None:
                surge_strikes.append({
                    "symbol": symbol,
                    "strike": strike,
                    "surge_type": surge_type,
                    "pe_change_pct": pe_chg_pct,
                    "ce_change_pct": ce_chg_pct,
                    "pe_oi": pe_oi,
                    "ce_oi": ce_oi,
                    "pe_ltp": pe_ltp,
                    "ce_ltp": ce_ltp,
                    "dist_pct": dist_pct,
                    "is_nearby": is_nearby,
                    "side": "PE" if has_pe_surge else "CE"
                })

        # Calculate PCR (Put Call Ratio)
        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0
        pcr_sentiment = "BULLISH" if pcr >= 1.2 else ("BEARISH" if pcr <= 0.8 else "NEUTRAL")

        # Max Pain Calculation
        min_loss = float("inf")
        max_pain_strike = spot_price
        for test_row in processed_strikes:
            t_strike = test_row["strike"]
            total_loss = 0
            for row in processed_strikes:
                s = row["strike"]
                # CE payout if spot settles at t_strike
                if t_strike > s:
                    total_loss += (t_strike - s) * row["ce_oi"]
                # PE payout if spot settles at t_strike
                if t_strike < s:
                    total_loss += (s - t_strike) * row["pe_oi"]
            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = t_strike

        # Distance to Heavy Resistance (Call Seller Wall) & Support (Put Seller Wall)
        ce_wall_dist_pct = round(((max_ce_strike - spot_price) / spot_price) * 100.0, 2) if (max_ce_strike and spot_price) else 0.0
        pe_wall_dist_pct = round(((spot_price - max_pe_strike) / spot_price) * 100.0, 2) if (max_pe_strike and spot_price) else 0.0

        return {
            "symbol": symbol,
            "spot_price": spot_price,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "total_ce_change": total_ce_change,
            "total_pe_change": total_pe_change,
            "pcr": pcr,
            "pcr_sentiment": pcr_sentiment,
            "max_pain": max_pain_strike,
            "heavy_call_writer_strike": max_ce_strike,
            "heavy_call_writer_oi": max_ce_oi,
            "ce_wall_dist_pct": ce_wall_dist_pct,
            "heavy_put_writer_strike": max_pe_strike,
            "heavy_put_writer_oi": max_pe_oi,
            "pe_wall_dist_pct": pe_wall_dist_pct,
            "highest_ce_oi_strike": max_ce_strike,
            "highest_pe_oi_strike": max_pe_strike,
            "surge_strikes": surge_strikes,
            "pe_oi_surge_options": pe_oi_surge_options,
            "ce_oi_surge_options": ce_oi_surge_options,
            "strikes": processed_strikes
        }
