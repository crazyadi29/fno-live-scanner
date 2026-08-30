class AlertDeck {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.seenSignalIds = new Set();
  }

  render(signals, audioEnabled = true) {
    if (!this.container) return;

    if (!signals || signals.length === 0) {
      this.container.innerHTML = `
        <div class="col-span-full py-8 text-center glass-panel rounded-xl border border-slate-800 text-slate-500">
          <div class="flex items-center justify-center space-x-2 text-sm font-medium">
            <svg class="w-5 h-5 animate-spin text-cyan-500" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span>Scanning FnO Universe for >100% PE/CE OI surges near Seller Walls...</span>
          </div>
        </div>
      `;
      return;
    }

    // Play chime on new signals
    let isNewAlert = false;
    for (const sig of signals) {
      if (!this.seenSignalIds.has(sig.id)) {
        this.seenSignalIds.add(sig.id);
        isNewAlert = true;
      }
    }

    if (isNewAlert && audioEnabled) {
      this.playAlertSound();
    }

    // Render cards
    let html = '';
    for (const sig of signals) {
      const isBullish = sig.type.includes('BULLISH');
      const cardClass = isBullish ? 'card-breakout-bullish' : 'card-breakout-bearish';
      const actionBadge = isBullish ? 'bg-emerald-500 text-black' : 'bg-rose-500 text-white';
      const surgeBadgeColor = isBullish ? 'text-emerald-400' : 'text-rose-400';

      html += `
        <div class="${cardClass} p-4 rounded-xl border relative overflow-hidden transition-all duration-300 hover:scale-[1.01] shadow-2xl">
          <!-- Top Badge Bar -->
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center space-x-2">
              <span class="px-2.5 py-1 rounded-md text-xs font-black tracking-wider uppercase ${actionBadge}">
                ${sig.action}
              </span>
              <span class="text-xs font-bold text-slate-300 font-mono">
                ${new Date(sig.timestamp * 1000).toLocaleTimeString()}
              </span>
            </div>
            <div class="flex items-center space-x-1.5 bg-slate-900/80 px-2 py-0.5 rounded-full border border-slate-700">
              <span class="text-[10px] text-slate-400 uppercase font-semibold">Win Prob:</span>
              <span class="text-xs font-black text-amber-400 font-mono">${sig.confidence}%</span>
            </div>
          </div>

          <!-- Main Option Strike Hero -->
          <div class="flex items-baseline justify-between mb-2">
            <div>
              <h3 class="text-xl font-black text-white tracking-tight flex items-center space-x-2">
                <span>${sig.recommended_option}</span>
                <span class="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-700 font-mono">
                  LTP ₹${sig.option_ltp.toFixed(2)}
                </span>
              </h3>
              <p class="text-xs text-slate-400 mt-0.5">
                Underlying Spot: <span class="font-mono font-bold text-slate-200">₹${sig.spot_ltp.toFixed(2)}</span>
              </p>
            </div>
          </div>

          <!-- Trigger Surge Details -->
          <div class="grid grid-cols-2 gap-2 my-3 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 font-mono text-xs">
            <div>
              <div class="text-[10px] text-slate-400">PE OI Surge Rate</div>
              <div class="text-sm font-black ${surgeBadgeColor}">
                +${sig.pe_oi_surge_pct ? sig.pe_oi_surge_pct.toFixed(1) : (sig.ce_oi_surge_pct ? sig.ce_oi_surge_pct.toFixed(1) : '100+')}%
              </div>
            </div>
            <div>
              <div class="text-[10px] text-slate-400">Call Seller Wall</div>
              <div class="text-sm font-bold text-amber-300">
                ${sig.ce_writer_wall || sig.pe_writer_wall} <span class="text-[10px] text-slate-400">(${sig.ce_wall_dist_pct}% away)</span>
              </div>
            </div>
          </div>

          <!-- Strategy Rationale -->
          <p class="text-xs text-slate-300 leading-relaxed font-sans mb-3 bg-slate-900/40 p-2 rounded border border-slate-800/80">
            ${sig.reason}
          </p>

          <!-- Quick Action Footer -->
          <div class="flex items-center justify-between pt-2 border-t border-slate-800/80">
            <span class="text-[11px] text-cyan-400 font-medium flex items-center space-x-1">
              <span>⚡ High OI Trap Detected</span>
            </span>
            <button onclick="window.selectStock('${sig.symbol}')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-semibold transition border border-slate-700">
              View Option Chain →
            </button>
          </div>
        </div>
      `;
    }

    this.container.innerHTML = html;
  }

  playAlertSound() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // A5
      osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.15); // E6
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
      console.log('Audio alert trigger failed', e);
    }
  }
}
window.AlertDeck = AlertDeck;
