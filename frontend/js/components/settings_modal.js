class SettingsModal {
  constructor(modalId) {
    this.modal = document.getElementById(modalId);
  }

  open() {
    if (this.modal) this.modal.classList.remove('hidden');
  }

  close() {
    if (this.modal) this.modal.classList.add('hidden');
  }

  async saveFyersCredentials(appId, token) {
    try {
      const resp = await fetch('/api/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          adapter: 'fyers',
          credentials: { app_id: appId, access_token: token }
        })
      });
      const data = await resp.json();
      return data;
    } catch (e) {
      console.error(e);
    }
  }

  async saveKiteCredentials(apiKey, token) {
    try {
      const resp = await fetch('/api/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          adapter: 'kite',
          credentials: { api_key: apiKey, access_token: token }
        })
      });
      const data = await resp.json();
      return data;
    } catch (e) {
      console.error(e);
    }
  }

  async switchAdapter(adapterName) {
    try {
      const resp = await fetch('/api/adapter/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adapter: adapterName })
      });
      return await resp.json();
    } catch (e) {
      console.error(e);
    }
  }

  async updateThresholds(peSurge, ceSurge, volMult, proxPct) {
    try {
      const resp = await fetch('/api/thresholds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pe_surge_threshold: parseFloat(peSurge),
          ce_surge_threshold: parseFloat(ceSurge),
          volume_surge_multiplier: parseFloat(volMult),
          writer_proximity_pct: parseFloat(proxPct)
        })
      });
      return await resp.json();
    } catch (e) {
      console.error(e);
    }
  }

  async triggerSimulatorSurge(symbol, strike, side, pct) {
    try {
      const resp = await fetch('/api/simulator/trigger-surge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol,
          strike: parseFloat(strike),
          side: side,
          surge_pct: parseFloat(pct)
        })
      });
      return await resp.json();
    } catch (e) {
      console.error(e);
    }
  }
}
window.SettingsModal = SettingsModal;
