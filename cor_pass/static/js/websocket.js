const WS_URL = "wss://dev-corid.cor-medical.ua/api/doctor/ws/signing" || API_BASE_URL; // <-- replace
const SESSION_TOKEN = '';      // <-- replace

let ws, heartbeat, reconnectTimer;
const backoff = { base: 1000, max: 10000, current: 0 };

function connect() {
    // Option A: pass token via query (if server supports it)
    const url = `${WS_URL}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
        console.log('[ws] connected');
        backoff.current = 0;
        // Option B: send auth message after open (if server expects it)
        // ws.send(JSON.stringify({ action: 'auth', session_token: SESSION_TOKEN }));

        // (optional) subscribe to a specific event type, if required by server
        // ws.send(JSON.stringify({ action: 'subscribe', event_type: 'signature_status' }));

        // Heartbeat ping every 30s (if server expects pings)

        heartbeat = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
            }
        }, 30000);
    };

    ws.onerror = (err) => {
        console.error('[ws] error', err);
    };

    ws.onclose = () => {
        console.warn('[ws] closed');
        clearInterval(heartbeat);
        // Exponential backoff reconnect
        backoff.current = Math.min(backoff.max, backoff.current ? backoff.current * 2 : backoff.base);
        reconnectTimer = setTimeout(connect, backoff.current);
    };
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    clearInterval(heartbeat);
    clearTimeout(reconnectTimer);
    if (ws && ws.readyState === WebSocket.OPEN) ws.close(1000, 'page unload');
});

// 3) Go!
connect();
