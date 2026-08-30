document.addEventListener('DOMContentLoaded', () => {
  // Initialize Components
  const alertDeck = new window.AlertDeck('alert-deck-container');
  const scannerTable = new window.ScannerTable('scanner-table-body');
  const oiMatrix = new window.OIMatrix('oi-matrix-container');
  const settingsModal = new window.SettingsModal('settings-modal');

  let audioEnabled = true;
  let currentSelectedSymbol = 'RELIANCE';
  let ws = null;
  let retryCount = 0;

  // DOM Elements
  const soundToggleBtn = document.getElementById('sound-toggle-btn');
  const connectionStatusBadge = document.getElementById('connection-status-badge');
  const modeBadge = document.getElementById('mode-badge');
  const searchInput = document.getElementById('stock-search-input');
  const filterButtons = document.querySelectorAll('.filter-btn');

  // Sound Toggle
  if (soundToggleBtn) {
    soundToggleBtn.addEventListener('click', () => {
      audioEnabled = !audioEnabled;
      soundToggleBtn.innerHTML = audioEnabled
        ? `<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path></svg><span class="text-xs font-semibold">Sound ON</span>`
        : `<svg class="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"></path></svg><span class="text-xs font-semibold text-slate-500">Sound OFF</span>`;
    });
  }

  // Filter Buttons
  filterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      filterButtons.forEach(b => {
        b.classList.remove('bg-cyan-500', 'text-black', 'font-black');
        b.classList.add('bg-slate-800', 'text-slate-300');
      });
      btn.classList.remove('bg-slate-800', 'text-slate-300');
      btn.classList.add('bg-cyan-500', 'text-black', 'font-black');
      
      const filter = btn.getAttribute('data-filter');
      scannerTable.setFilter(filter);
    });
  });

  // Search Input
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      scannerTable.setSearchQuery(e.target.value);
    });
  }

  // Stock Selector Global
  window.selectStock = async (symbol) => {
    currentSelectedSymbol = symbol;
    scannerTable.selectedSymbol = symbol;
    try {
      const resp = await fetch(`/api/stock/${symbol}/details`);
      if (resp.ok) {
        const details = await resp.json();
        oiMatrix.render(details);
        document.getElementById('oi-matrix-section')?.scrollIntoView({ behavior: 'smooth' });
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Connect WebSocket
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/scanner`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      retryCount = 0;
      if (connectionStatusBadge) {
        connectionStatusBadge.innerHTML = `
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 live-dot"></span>
          <span class="text-xs font-bold text-emerald-400 font-mono">LIVE FEED CONNECTED</span>
        `;
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'SCANNER_UPDATE') {
          if (modeBadge) {
            modeBadge.innerText = data.mode.toUpperCase();
          }

          alertDeck.render(data.breakout_signals, audioEnabled);
          scannerTable.render(data.stocks, data.surge_strikes);

          if (currentSelectedSymbol) {
            const currentStockObj = data.stocks.find(s => s.symbol === currentSelectedSymbol);
            if (currentStockObj) {
              fetch(`/api/stock/${currentSelectedSymbol}/details`)
                .then(r => r.json())
                .then(details => oiMatrix.render(details))
                .catch(() => {});
            }
          }
        }
      } catch (e) {
        console.error('Error handling WS message', e);
      }
    };

    ws.onclose = () => {
      if (connectionStatusBadge) {
        connectionStatusBadge.innerHTML = `
          <span class="w-2 h-2 rounded-full bg-amber-500"></span>
          <span class="text-xs font-semibold text-amber-400 font-mono">RECONNECTING...</span>
        `;
      }
      retryCount++;
      const delay = Math.min(5000, 1000 * Math.pow(1.5, retryCount));
      setTimeout(connectWebSocket, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  // Initial Connect & Load
  connectWebSocket();
  window.selectStock('RELIANCE');

  // Modal Buttons
  const openSettingsBtn = document.getElementById('open-settings-btn');
  const closeSettingsBtn = document.getElementById('close-settings-btn');
  const openSimSurgeBtn = document.getElementById('open-sim-surge-btn');

  if (openSettingsBtn) openSettingsBtn.addEventListener('click', () => settingsModal.open());
  if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', () => settingsModal.close());

  // 1-Click Buttons
  const btnFyers1Click = document.getElementById('btn-fyers-1click');
  if (btnFyers1Click) {
    btnFyers1Click.addEventListener('click', () => settingsModal.launchFyersOneClickLogin());
  }

  const btnKite1Click = document.getElementById('btn-kite-1click');
  if (btnKite1Click) {
    btnKite1Click.addEventListener('click', () => settingsModal.launchKiteOneClickLogin());
  }

  // Switch to Simulator Button
  const switchSimBtn = document.getElementById('switch-sim-btn');
  if (switchSimBtn) {
    switchSimBtn.addEventListener('click', async () => {
      await settingsModal.switchAdapter('simulator');
      alert('Switched to Live Market Simulator mode!');
      settingsModal.close();
    });
  }

  // Quick Trigger Surge Button
  if (openSimSurgeBtn) {
    openSimSurgeBtn.addEventListener('click', async () => {
      const sym = prompt("Enter Symbol to inject >100% surge (e.g. RELIANCE, NIFTY, BANKNIFTY, HDFCBANK, TATAMOTORS):", currentSelectedSymbol || "RELIANCE");
      if (!sym) return;
      const side = prompt("Surge side (PE or CE):", "PE");
      if (!side) return;
      const pct = prompt("Surge % (e.g. 145):", "145");
      if (!pct) return;

      const resp = await settingsModal.triggerSimulatorSurge(sym.toUpperCase(), 0, side.toUpperCase(), pct);
      alert(resp?.message || "Surge triggered!");
    });
  }

  // Thresholds Form
  const thresholdsForm = document.getElementById('thresholds-form');
  if (thresholdsForm) {
    thresholdsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const peVal = document.getElementById('thresh-pe-oi').value;
      const ceVal = document.getElementById('thresh-ce-oi').value;
      const volVal = document.getElementById('thresh-vol-mult').value;
      const proxVal = document.getElementById('thresh-prox-pct').value;
      await settingsModal.updateThresholds(peVal, ceVal, volVal, proxVal);
      alert('Strategy thresholds updated successfully!');
      settingsModal.close();
    });
  }
});
