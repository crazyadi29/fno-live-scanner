class OIMatrix {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  render(stockDetails) {
    if (!this.container) return;

    if (!stockDetails) {
      this.container.innerHTML = `
        <div class="py-16 text-center text-slate-500 glass-panel rounded-xl">
          Select any stock from the scanner table above to inspect live Option Chain & OI Depth Matrix
        </div>
      `;
      return;
    }

    const s = stockDetails.symbol;
    const spot = stockDetails.technicals.ltp;
    const strikes = stockDetails.strikes || [];
    const oiSummary = stockDetails.oi_summary || {};
    const tech = stockDetails.technicals || {};

    // Find max OI for proportional bar widths
    let maxOI = 1;
    for (const row of strikes) {
      if (row.ce_oi > maxOI) maxOI = row.ce_oi;
      if (row.pe_oi > maxOI) maxOI = row.pe_oi;
    }

    let rowsHtml = '';
    for (const row of strikes) {
      const strikeVal = row.strike;
      const isAtm = Math.abs(strikeVal - spot) <= (strikes[1]?.strike - strikes[0]?.strike || 50) * 0.5;
      const isHeavyCE = (strikeVal === oiSummary.heavy_ce_wall);
      const isHeavyPE = (strikeVal === oiSummary.heavy_pe_wall);

      const ceBarWidth = Math.min(100, Math.round((row.ce_oi / maxOI) * 100));
      const peBarWidth = Math.min(100, Math.round((row.pe_oi / maxOI) * 100));

      const isPESurge = row.pe_change_pct >= 100;
      const isCESurge = row.ce_change_pct >= 100;

      const ceChgColor = row.ce_change_oi >= 0 ? 'text-emerald-400' : 'text-rose-400';
      const peChgColor = row.pe_change_oi >= 0 ? 'text-emerald-400' : 'text-rose-400';

      const rowClass = isAtm ? 'atm-strike-row' : (isHeavyCE || isHeavyPE ? 'heavy-seller-strike' : '');

      rowsHtml += `
        <tr class="border-b border-slate-800/40 text-xs font-mono transition ${rowClass}">
          <!-- CALL OI VISUAL BAR & NUMBER -->
          <td class="py-2 px-3 text-right relative w-1/4">
            <div class="absolute inset-y-0 right-0 oi-bar-ce" style="width: ${ceBarWidth}%;"></div>
            <div class="relative z-10 flex items-center justify-end space-x-2">
              ${isCESurge ? '<span class="px-1.5 py-0.2 rounded bg-rose-500 text-black text-[9px] font-black animate-pulse">🔥 +'+row.ce_change_pct+'%</span>' : ''}
              ${isHeavyCE ? '<span class="text-[9px] font-bold text-amber-400 bg-amber-950/80 px-1 rounded border border-amber-500/40">RESISTANCE</span>' : ''}
              <span class="font-bold text-slate-200">${(row.ce_oi / 1000).toFixed(0)}k</span>
            </div>
          </td>

          <!-- CALL CHG OI -->
          <td class="py-2 px-2 text-right ${ceChgColor}">
            ${row.ce_change_oi > 0 ? '+' : ''}${(row.ce_change_oi / 1000).toFixed(1)}k
            <span class="text-[10px] text-slate-500">(${row.ce_change_pct}%)</span>
          </td>

          <!-- CALL LTP -->
          <td class="py-2 px-2 text-right font-bold text-cyan-300">
            ₹${row.ce_ltp.toFixed(2)}
          </td>

          <!-- STRIKE CENTER PILL -->
          <td class="py-2 px-3 text-center font-black ${isAtm ? 'text-cyan-300 bg-cyan-950/60 rounded' : 'text-white bg-slate-900/80'} border-x border-slate-800">
            ${strikeVal}
            ${isAtm ? '<span class="block text-[8px] font-sans text-cyan-400">ATM</span>' : ''}
          </td>

          <!-- PUT LTP -->
          <td class="py-2 px-2 text-left font-bold text-cyan-300">
            ₹${row.pe_ltp.toFixed(2)}
          </td>

          <!-- PUT CHG OI -->
          <td class="py-2 px-2 text-left ${peChgColor}">
            ${row.pe_change_oi > 0 ? '+' : ''}${(row.pe_change_oi / 1000).toFixed(1)}k
            <span class="text-[10px] text-slate-500">(${row.pe_change_pct}%)</span>
          </td>

          <!-- PUT OI VISUAL BAR & NUMBER -->
          <td class="py-2 px-3 text-left relative w-1/4">
            <div class="absolute inset-y-0 left-0 oi-bar-pe" style="width: ${peBarWidth}%;"></div>
            <div class="relative z-10 flex items-center justify-start space-x-2">
              <span class="font-bold text-slate-200">${(row.pe_oi / 1000).toFixed(0)}k</span>
              ${isHeavyPE ? '<span class="text-[9px] font-bold text-emerald-400 bg-emerald-950/80 px-1 rounded border border-emerald-500/40">SUPPORT</span>' : ''}
              ${isPESurge ? '<span class="px-1.5 py-0.2 rounded bg-emerald-500 text-black text-[9px] font-black animate-pulse">🔥 +'+row.pe_change_pct+'%</span>' : ''}
            </div>
          </td>
        </tr>
      `;
    }

    this.container.innerHTML = `
      <div class="glass-panel rounded-xl border border-slate-800 p-5">
        <!-- Stock Details Header Bar -->
        <div class="flex flex-wrap items-center justify-between gap-4 pb-4 mb-4 border-b border-slate-800">
          <div>
            <div class="flex items-center space-x-3">
              <h2 class="text-2xl font-black text-white font-mono">${s}</h2>
              <span class="px-2.5 py-0.5 rounded text-xs font-bold ${tech.change_pct >= 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">
                ₹${spot.toFixed(2)} (${tech.change_pct >= 0 ? '+' : ''}${tech.change_pct}%)
              </span>
              <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold">
                VWAP: ₹${tech.vwap}
              </span>
              <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold">
                RSI: ${tech.rsi}
              </span>
            </div>
            <div class="text-xs text-slate-400 mt-1 flex space-x-4">
              <span>EMA(9): <strong class="text-slate-200">₹${tech.ema9}</strong></span>
              <span>EMA(21): <strong class="text-slate-200">₹${tech.ema21}</strong></span>
              <span>Max Pain: <strong class="text-amber-400">₹${oiSummary.max_pain}</strong></span>
            </div>
          </div>

          <!-- Total OI & PCR Summary -->
          <div class="flex items-center space-x-6 text-xs font-mono">
            <div class="text-right">
              <div class="text-slate-500 text-[11px]">Total CE OI (Sellers)</div>
              <div class="text-sm font-bold text-rose-400">${(oiSummary.total_ce_oi / 100000).toFixed(1)}L</div>
            </div>
            <div class="text-center px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800">
              <div class="text-slate-500 text-[10px]">PCR (Sentiment)</div>
              <div class="text-sm font-black ${oiSummary.pcr >= 1.2 ? 'text-emerald-400' : 'text-slate-200'}">
                ${oiSummary.pcr.toFixed(2)} <span class="text-[10px] font-sans font-normal text-slate-400">(${oiSummary.pcr_sentiment})</span>
              </div>
            </div>
            <div class="text-left">
              <div class="text-slate-500 text-[11px]">Total PE OI (Supporters)</div>
              <div class="text-sm font-bold text-emerald-400">${(oiSummary.total_pe_oi / 100000).toFixed(1)}L</div>
            </div>
          </div>
        </div>

        <!-- Matrix Table -->
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800 bg-slate-900/50">
                <th class="py-2.5 px-3 text-right">Call OI (Resistance)</th>
                <th class="py-2.5 px-2 text-right">CE Chg OI</th>
                <th class="py-2.5 px-2 text-right">CE LTP</th>
                <th class="py-2.5 px-3 text-center bg-slate-900 border-x border-slate-800">STRIKE</th>
                <th class="py-2.5 px-2 text-left">PE LTP</th>
                <th class="py-2.5 px-2 text-left">PE Chg OI</th>
                <th class="py-2.5 px-3 text-left">Put OI (Support)</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }
}
window.OIMatrix = OIMatrix;
