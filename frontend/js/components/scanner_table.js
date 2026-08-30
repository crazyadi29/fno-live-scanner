class ScannerTable {
  constructor(tableBodyId) {
    this.tableBody = document.getElementById(tableBodyId);
    this.currentFilter = 'ALL';
    this.searchQuery = '';
    this.selectedSymbol = null;
  }

  setFilter(filter) {
    this.currentFilter = filter;
  }

  setSearchQuery(q) {
    this.searchQuery = q.toUpperCase().trim();
  }

  render(stocks, surges) {
    if (!this.tableBody) return;

    if (!stocks || stocks.length === 0) {
      this.tableBody.innerHTML = `
        <tr>
          <td colspan="9" class="text-center py-12 text-slate-500">
            Waiting for live market ticks...
          </td>
        </tr>
      `;
      return;
    }

    // Build surge map for rapid lookup
    const surgeMap = {};
    if (surges) {
      for (const s of surges) {
        if (!surgeMap[s.symbol]) surgeMap[s.symbol] = [];
        surgeMap[s.symbol].push(s);
      }
    }

    // Filter stocks
    const filtered = stocks.filter(stock => {
      if (this.searchQuery && !stock.symbol.includes(this.searchQuery)) {
        return false;
      }
      const hasPESurge = (surgeMap[stock.symbol] || []).some(s => s.pe_change_pct >= 100);
      const hasCESurge = (surgeMap[stock.symbol] || []).some(s => s.ce_change_pct >= 100);
      const isVolSurge = stock.volume_surge && stock.volume_surge.surge_ratio >= 2.0;
      const isBullish = stock.momentum.includes('BULLISH');

      if (this.currentFilter === 'BULLISH_BREAKOUT') {
        return isBullish && (hasPESurge || isVolSurge);
      } else if (this.currentFilter === 'PE_OI_SURGE') {
        return hasPESurge;
      } else if (this.currentFilter === 'CE_OI_SURGE') {
        return hasCESurge;
      } else if (this.currentFilter === 'VOLUME_SURGE') {
        return isVolSurge;
      }
      return true;
    });

    let html = '';
    for (const s of filtered) {
      const isSelected = (this.selectedSymbol === s.symbol);
      const isPositive = s.change_pct >= 0;
      const chgColor = isPositive ? 'text-emerald-400' : 'text-rose-400';
      const chgSign = isPositive ? '+' : '';
      
      const stockSurges = surgeMap[s.symbol] || [];
      const peSurge = stockSurges.find(x => x.pe_change_pct >= 100);
      const ceSurge = stockSurges.find(x => x.ce_change_pct >= 100);

      // Momentum Badge
      let momBadge = '';
      if (s.momentum === 'BULLISH_BREAKOUT') {
        momBadge = '<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[11px] font-bold">🚀 BREAKOUT</span>';
      } else if (s.momentum === 'BULLISH_STRONG') {
        momBadge = '<span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-semibold">BULLISH</span>';
      } else if (s.momentum.includes('BEARISH')) {
        momBadge = '<span class="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[11px] font-semibold">BEARISH</span>';
      } else {
        momBadge = '<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[11px]">NEUTRAL</span>';
      }

      // Volume Surge Multiplier
      const volRatio = s.volume_surge ? s.volume_surge.surge_ratio : 1.0;
      const volBadge = volRatio >= 2.5
        ? `<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono font-bold text-xs border border-amber-500/40 animate-pulse">⚡ ${volRatio}x</span>`
        : `<span class="font-mono text-xs text-slate-400">${volRatio}x</span>`;

      // OI Surge Indicators
      let surgePill = '';
      if (peSurge) {
        surgePill += `<span class="px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-600 font-mono text-[10px] font-black mr-1">PE +${peSurge.pe_change_pct.toFixed(0)}%</span>`;
      }
      if (ceSurge) {
        surgePill += `<span class="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-600 font-mono text-[10px] font-black">CE +${ceSurge.ce_change_pct.toFixed(0)}%</span>`;
      }
      if (!surgePill) {
        surgePill = '<span class="text-slate-600 text-xs">-</span>';
      }

      // Resistance & Support Walls
      const ceWall = s.oi_summary.heavy_ce_wall ? `${s.oi_summary.heavy_ce_wall} (${s.oi_summary.ce_wall_dist_pct}%)` : '-';
      const peWall = s.oi_summary.heavy_pe_wall ? `${s.oi_summary.heavy_pe_wall} (${s.oi_summary.pe_wall_dist_pct}%)` : '-';

      // PCR Badge
      const pcrVal = s.oi_summary.pcr.toFixed(2);
      const pcrColor = s.oi_summary.pcr >= 1.2 ? 'text-emerald-400' : (s.oi_summary.pcr <= 0.8 ? 'text-rose-400' : 'text-slate-300');

      html += `
        <tr onclick="window.selectStock('${s.symbol}')" class="cursor-pointer border-b border-slate-800/60 transition-colors ${isSelected ? 'bg-cyan-950/30 border-cyan-500/40' : 'hover:bg-slate-850 hover:bg-opacity-50'}">
          <!-- Symbol & Surge Tag -->
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <span class="font-bold text-white tracking-wide text-sm font-mono">${s.symbol}</span>
              ${peSurge ? '<span class="w-2 h-2 rounded-full bg-emerald-400 live-dot"></span>' : ''}
            </div>
            <div class="mt-1">${surgePill}</div>
          </td>

          <!-- Spot LTP & Change -->
          <td class="py-3 px-4 font-mono text-right">
            <div class="text-sm font-bold text-white">₹${s.ltp.toFixed(2)}</div>
            <div class="text-xs ${chgColor} font-semibold">${chgSign}${s.change_pct.toFixed(2)}%</div>
          </td>

          <!-- Technicals: VWAP & RSI -->
          <td class="py-3 px-4 font-mono text-xs">
            <div class="flex items-center justify-between text-slate-300">
              <span class="text-slate-500">VWAP:</span>
              <span class="${s.ltp >= s.vwap ? 'text-emerald-400 font-bold' : 'text-rose-400'}">₹${s.vwap}</span>
            </div>
            <div class="flex items-center justify-between text-slate-300 mt-0.5">
              <span class="text-slate-500">RSI(14):</span>
              <span class="${s.rsi >= 55 ? 'text-emerald-400 font-bold' : (s.rsi <= 45 ? 'text-rose-400' : 'text-slate-300')}">${s.rsi}</span>
            </div>
          </td>

          <!-- Vol Surge -->
          <td class="py-3 px-4 text-center">
            ${volBadge}
          </td>

          <!-- Call Seller Wall (Resistance) -->
          <td class="py-3 px-4 font-mono text-xs text-rose-300">
            <div class="font-semibold">${ceWall}</div>
            <div class="text-[10px] text-slate-500">${(s.oi_summary.heavy_ce_oi / 100000).toFixed(1)}L OI</div>
          </td>

          <!-- Put Seller Wall (Support) -->
          <td class="py-3 px-4 font-mono text-xs text-emerald-300">
            <div class="font-semibold">${peWall}</div>
            <div class="text-[10px] text-slate-500">${(s.oi_summary.heavy_pe_oi / 100000).toFixed(1)}L OI</div>
          </td>

          <!-- PCR -->
          <td class="py-3 px-4 font-mono text-center text-xs font-bold ${pcrColor}">
            ${pcrVal}
            <div class="text-[9px] text-slate-500 uppercase">${s.oi_summary.pcr_sentiment}</div>
          </td>

          <!-- Momentum -->
          <td class="py-3 px-4 text-center">
            ${momBadge}
          </td>

          <!-- Action -->
          <td class="py-3 px-4 text-right">
            <button class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-cyan-900 hover:text-cyan-200 text-slate-300 rounded border border-slate-700 font-medium transition">
              Option Chain
            </button>
          </td>
        </tr>
      `;
    }

    this.tableBody.innerHTML = html;
  }
}
window.ScannerTable = ScannerTable;
