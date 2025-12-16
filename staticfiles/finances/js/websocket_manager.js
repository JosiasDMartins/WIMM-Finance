/**
 * WebSocket Manager for Real-time Updates
 * Handles connection, reconnection, and message routing
 */
class WebSocketManager {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.messageHandlers = {};
        this.connectionStatusCallbacks = [];
        this.isIntentionallyClosed = false;
        this.pingInterval = null;
    }

    connect() {
        // Determine protocol (ws:// or wss://)
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';

        // Extract hostname without port
        const hostname = window.location.hostname;

        // Build WebSocket URL
        let wsUrl;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            // Development: connect directly to Daphne port
            wsUrl = wsProtocol + hostname + ':8000/ws/updates/';
        } else {
            // Production: use same host (requires reverse proxy configuration)
            wsUrl = wsProtocol + window.location.host + '/ws/updates/';
        }

        console.log('[WebSocket] Connecting to:', wsUrl);

        try {
            this.socket = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this.scheduleReconnect();
        }
    }

    setupEventHandlers() {
        this.socket.onopen = (event) => {
            console.log('[WebSocket] Connected successfully');
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            this.notifyConnectionStatus('connected');

            // Start ping interval for connection health
            this.startPingInterval();
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('[WebSocket] Message received:', data);

                // Route to appropriate handler
                this.routeMessage(data);
            } catch (error) {
                console.error('[WebSocket] Failed to parse message:', error);
            }
        };

        this.socket.onclose = (event) => {
            console.log('[WebSocket] Connection closed:', event.code, event.reason);
            this.notifyConnectionStatus('disconnected');
            this.stopPingInterval();

            // Attempt reconnection unless intentionally closed
            if (!this.isIntentionallyClosed) {
                this.scheduleReconnect();
            }
        };

        this.socket.onerror = (error) => {
            console.error('[WebSocket] Error:', error);
            this.notifyConnectionStatus('error');
        };
    }

    startPingInterval() {
        // Send ping every 30 seconds to keep connection alive
        this.pingInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({
                    type: 'ping',
                    timestamp: Date.now()
                }));
            }
        }, 30000);
    }

    stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[WebSocket] Max reconnection attempts reached');
            this.notifyConnectionStatus('failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    routeMessage(data) {
        const messageType = data.type;

        if (messageType === 'pong') {
            // Handle pong response
            return;
        }

        // Call registered handlers for this message type
        const handlers = this.messageHandlers[messageType] || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`[WebSocket] Handler error for ${messageType}:`, error);
            }
        });
    }

    registerHandler(messageType, handler) {
        if (!this.messageHandlers[messageType]) {
            this.messageHandlers[messageType] = [];
        }
        this.messageHandlers[messageType].push(handler);
    }

    unregisterHandler(messageType, handler) {
        if (this.messageHandlers[messageType]) {
            this.messageHandlers[messageType] = this.messageHandlers[messageType]
                .filter(h => h !== handler);
        }
    }

    onConnectionStatus(callback) {
        this.connectionStatusCallbacks.push(callback);
    }

    notifyConnectionStatus(status) {
        this.connectionStatusCallbacks.forEach(callback => {
            try {
                callback(status);
            } catch (error) {
                console.error('[WebSocket] Connection status callback error:', error);
            }
        });
    }

    disconnect() {
        this.isIntentionallyClosed = true;
        this.stopPingInterval();
        if (this.socket) {
            this.socket.close();
        }
    }
}

// Create global instance
window.wsManager = new WebSocketManager();
