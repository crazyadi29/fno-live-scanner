class SettingsModal {
  constructor(modalId) {
    this.modal = document.getElementById(modalId);
    this.loadSavedCredentials();
    this.listenForOAuthMessages();
  }

  open() {
    if (this.modal) {
      this.modal.classList.remove('hidden');
      this.updateRedirectUriLabels();
    }
  }

  close() {
    if (this.modal) this.modal.classList.add('hidden');
  }

  updateRedirectUriLabels() {
    const currentOrigin = window.location.origin;
    const fyersCb = `${currentOrigin}/api/auth/fyers/callback`;
    const kiteCb = `${currentOrigin}/api/auth/kite/callback`;

    const elFyersCb = document.getElementById('fyers-redirect-uri-display');
    const elKiteCb = document.getElementById('kite-redirect-uri-display');

    if (elFyersCb) elFyersCb.innerText = fyersCb;
    if (elKiteCb) elKiteCb.innerText = kiteCb;
  }

  loadSavedCredentials() {
    const fyersAppId = localStorage.getItem('fyers_app_id') || '';
    const fyersSecret = localStorage.getItem('fyers_app_secret') || '';
    const kiteKey = localStorage.getItem('kite_api_key') || '';
    const kiteSecret = localStorage.getItem('kite_api_secret') || '';

    const elFyersId = document.getElementById('fyers-app-id');
    const elFyersSec = document.getElementById('fyers-app-secret');
    const elKiteKey = document.getElementById('kite-api-key');
    const elKiteSec = document.getElementById('kite-api-secret');

    if (elFyersId) elFyersId.value = fyersAppId;
    if (elFyersSec) elFyersSec.value = fyersSecret;
    if (elKiteKey) elKiteKey.value = kiteKey;
    if (elKiteSec) elKiteSec.value = kiteSecret;
  }

  saveFormCredentials() {
    const fyersAppId = document.getElementById('fyers-app-id')?.value.trim() || '';
    const fyersSecret = document.getElementById('fyers-app-secret')?.value.trim() || '';
    const kiteKey = document.getElementById('kite-api-key')?.value.trim() || '';
    const kiteSecret = document.getElementById('kite-api-secret')?.value.trim() || '';

    if (fyersAppId) localStorage.setItem('fyers_app_id', fyersAppId);
    if (fyersSecret) localStorage.setItem('fyers_app_secret', fyersSecret);
    if (kiteKey) localStorage.setItem('kite_api_key', kiteKey);
    if (kiteSecret) localStorage.setItem('kite_api_secret', kiteSecret);
  }

  listenForOAuthMessages() {
    window.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'BROKER_CONNECTED') {
        const broker = event.data.broker;
        const modeBadge = document.getElementById('mode-badge');
        if (modeBadge) modeBadge.innerText = broker.toUpperCase();

        const connBadge = document.getElementById('connection-status-badge');
        if (connBadge) {
          connBadge.innerHTML = `
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 live-dot"></span>
            <span class="text-xs font-bold text-emerald-400 font-mono">LIVE FEED (${broker.toUpperCase()})</span>
          `;
        }

        alert(`🎉 1-Click Login Successful!\n${broker.toUpperCase()} daily access token generated and connected automatically.`);
        this.close();
      }
    });
  }

  async launchFyersOneClickLogin() {
    let appId = document.getElementById('fyers-app-id')?.value.trim();
    const appSecret = document.getElementById('fyers-app-secret')?.value.trim();

    if (!appId || !appSecret) {
      alert("Please enter your Fyers App ID and Secret Key first.");
      return;
    }

    if (!appId.endsWith("-100") && !appId.includes("-") && appId.length > 2) {
      appId = appId + "-100";
      const el = document.getElementById('fyers-app-id');
      if (el) el.value = appId;
    }

    this.saveFormCredentials();

    try {
      const resp = await fetch(`/api/auth/fyers/login-url?app_id=${encodeURIComponent(appId)}&app_secret=${encodeURIComponent(appSecret)}`);
      const data = await resp.json();
      if (data.auth_url) {
        const w = 550;
        const h = 700;
        const left = (screen.width / 2) - (w / 2);
        const top = (screen.height / 2) - (h / 2);
        window.open(data.auth_url, 'FyersOAuth', `width=${w},height=${h},top=${top},left=${left},scrollbars=yes`);
      }
    } catch (e) {
      alert("Error initiating Fyers login: " + e.message);
    }
  }

  async manualExchangeFyers() {
    const appId = document.getElementById('fyers-app-id')?.value.trim();
    const appSecret = document.getElementById('fyers-app-secret')?.value.trim();
    const authCodeInput = document.getElementById('fyers-manual-code')?.value.trim();

    if (!authCodeInput) {
      alert("Please paste the redirected URL or auth_code from your browser.");
      return;
    }

    try {
      const resp = await fetch('/api/auth/fyers/exchange-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          app_id: appId,
          app_secret: appSecret,
          auth_code: authCodeInput
        })
      });
      const data = await resp.json();
      if (resp.ok && data.status === 'success') {
        alert("🎉 Fyers Connected Successfully!");
        const modeBadge = document.getElementById('mode-badge');
        if (modeBadge) modeBadge.innerText = 'FYERS';
        this.close();
      } else {
        alert("Exchange error: " + (data.detail || JSON.stringify(data)));
      }
    } catch (e) {
      alert("Exchange failed: " + e.message);
    }
  }

  async launchKiteOneClickLogin() {
    const apiKey = document.getElementById('kite-api-key')?.value.trim();
    const apiSecret = document.getElementById('kite-api-secret')?.value.trim();

    if (!apiKey || !apiSecret) {
      alert("Please enter your Kite API Key and Secret first.");
      return;
    }

    this.saveFormCredentials();

    try {
      const resp = await fetch(`/api/auth/kite/login-url?api_key=${encodeURIComponent(apiKey)}&api_secret=${encodeURIComponent(apiSecret)}`);
      const data = await resp.json();
      if (data.auth_url) {
        const w = 550;
        const h = 700;
        const left = (screen.width / 2) - (w / 2);
        const top = (screen.height / 2) - (h / 2);
        window.open(data.auth_url, 'KiteOAuth', `width=${w},height=${h},top=${top},left=${left},scrollbars=yes`);
      }
    } catch (e) {
      alert("Error initiating Kite login: " + e.message);
    }
  }

  async manualExchangeKite() {
    const apiKey = document.getElementById('kite-api-key')?.value.trim();
    const apiSecret = document.getElementById('kite-api-secret')?.value.trim();
    const reqTokenInput = document.getElementById('kite-manual-code')?.value.trim();

    if (!reqTokenInput) {
      alert("Please paste the redirected URL or request_token from your browser.");
      return;
    }

    try {
      const resp = await fetch('/api/auth/kite/exchange-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          api_secret: apiSecret,
          request_token: reqTokenInput
        })
      });
      const data = await resp.json();
      if (resp.ok && data.status === 'success') {
        alert("🎉 Zerodha Kite Connected Successfully!");
        const modeBadge = document.getElementById('mode-badge');
        if (modeBadge) modeBadge.innerText = 'KITE';
        this.close();
      } else {
        alert("Exchange error: " + (data.detail || JSON.stringify(data)));
      }
    } catch (e) {
      alert("Exchange failed: " + e.message);
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
