"""
WebSocket Security Module

Implements security features for WebSocket connections:
- Rate limiting to prevent abuse
- Connection timeout monitoring
- Heartbeat/keepalive checking
"""

import time
import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class WebSocketRateLimiter:
    """
    Rate limiter for WebSocket connections.

    Tracks connection attempts per user to prevent abuse.
    Uses Django cache backend for distributed rate limiting.
    """

    @staticmethod
    def get_cache_key(user_id):
        """Generate cache key for user rate limiting."""
        return f'ws_rate_limit:user:{user_id}'

    @staticmethod
    def check_connection_rate(user_id, max_attempts=None, window_seconds=None):
        """
        Check if user has exceeded connection rate limit.

        Args:
            user_id: User ID to check
            max_attempts: Maximum attempts allowed (default from settings)
            window_seconds: Time window in seconds (default from settings)

        Returns:
            tuple: (allowed: bool, retry_after: int or None)
                - allowed: True if connection is allowed
                - retry_after: Seconds to wait before retry (None if allowed)
        """
        if max_attempts is None:
            max_attempts = getattr(settings, 'WS_RATE_LIMIT_MAX_ATTEMPTS', 10)

        if window_seconds is None:
            window_seconds = getattr(settings, 'WS_RATE_LIMIT_WINDOW_SECONDS', 60)

        cache_key = WebSocketRateLimiter.get_cache_key(user_id)

        # Get current attempt count
        attempts_data = cache.get(cache_key)

        if attempts_data is None:
            # First attempt
            attempts_data = {
                'count': 1,
                'first_attempt': time.time()
            }
            cache.set(cache_key, attempts_data, window_seconds)
            logger.debug(f"[WS_RATE_LIMIT] User {user_id}: First attempt tracked")
            return True, None

        # Check if window has expired
        time_elapsed = time.time() - attempts_data['first_attempt']

        if time_elapsed > window_seconds:
            # Window expired, reset counter
            attempts_data = {
                'count': 1,
                'first_attempt': time.time()
            }
            cache.set(cache_key, attempts_data, window_seconds)
            logger.debug(f"[WS_RATE_LIMIT] User {user_id}: Window expired, reset counter")
            return True, None

        # Check if limit exceeded
        if attempts_data['count'] >= max_attempts:
            retry_after = int(window_seconds - time_elapsed)
            logger.warning(
                f"[WS_RATE_LIMIT] User {user_id}: Rate limit exceeded "
                f"({attempts_data['count']}/{max_attempts}). "
                f"Retry after {retry_after}s"
            )
            return False, retry_after

        # Increment counter
        attempts_data['count'] += 1
        cache.set(cache_key, attempts_data, window_seconds)

        logger.debug(
            f"[WS_RATE_LIMIT] User {user_id}: Attempt {attempts_data['count']}/{max_attempts}"
        )
        return True, None

    @staticmethod
    def reset_user_limit(user_id):
        """Reset rate limit for a specific user."""
        cache_key = WebSocketRateLimiter.get_cache_key(user_id)
        cache.delete(cache_key)
        logger.info(f"[WS_RATE_LIMIT] User {user_id}: Rate limit reset")


class WebSocketConnectionMonitor:
    """
    Monitor WebSocket connection health.

    Tracks connection timestamps and heartbeat status.
    """

    @staticmethod
    def get_connection_key(user_id, channel_name):
        """Generate cache key for connection monitoring."""
        return f'ws_monitor:user:{user_id}:channel:{channel_name}'

    @staticmethod
    def register_connection(user_id, channel_name):
        """
        Register a new WebSocket connection.

        Args:
            user_id: User ID
            channel_name: Unique channel identifier
        """
        cache_key = WebSocketConnectionMonitor.get_connection_key(user_id, channel_name)

        connection_data = {
            'user_id': user_id,
            'channel_name': channel_name,
            'connected_at': time.time(),
            'last_heartbeat': time.time(),
            'heartbeat_failures': 0
        }

        timeout = getattr(settings, 'WS_CONNECTION_TIMEOUT', 3600)
        cache.set(cache_key, connection_data, timeout)

        logger.info(f"[WS_MONITOR] User {user_id}: Connection registered ({channel_name})")

    @staticmethod
    def update_heartbeat(user_id, channel_name):
        """
        Update heartbeat timestamp for a connection.

        Args:
            user_id: User ID
            channel_name: Channel identifier

        Returns:
            bool: True if connection exists and updated, False otherwise
        """
        cache_key = WebSocketConnectionMonitor.get_connection_key(user_id, channel_name)
        connection_data = cache.get(cache_key)

        if connection_data is None:
            logger.warning(
                f"[WS_MONITOR] User {user_id}: Heartbeat for unknown connection ({channel_name})"
            )
            return False

        connection_data['last_heartbeat'] = time.time()
        connection_data['heartbeat_failures'] = 0

        timeout = getattr(settings, 'WS_CONNECTION_TIMEOUT', 3600)
        cache.set(cache_key, connection_data, timeout)

        return True

    @staticmethod
    def check_connection_health(user_id, channel_name):
        """
        Check if connection is healthy based on heartbeat.

        Args:
            user_id: User ID
            channel_name: Channel identifier

        Returns:
            tuple: (is_healthy: bool, time_since_heartbeat: float or None)
        """
        cache_key = WebSocketConnectionMonitor.get_connection_key(user_id, channel_name)
        connection_data = cache.get(cache_key)

        if connection_data is None:
            return False, None

        time_since_heartbeat = time.time() - connection_data['last_heartbeat']
        heartbeat_interval = getattr(settings, 'WS_HEARTBEAT_INTERVAL', 30)

        # Consider unhealthy if no heartbeat for 3x the interval
        is_healthy = time_since_heartbeat < (heartbeat_interval * 3)

        if not is_healthy:
            logger.warning(
                f"[WS_MONITOR] User {user_id}: Unhealthy connection - "
                f"{time_since_heartbeat:.1f}s since last heartbeat"
            )

        return is_healthy, time_since_heartbeat

    @staticmethod
    def unregister_connection(user_id, channel_name):
        """
        Unregister a WebSocket connection.

        Args:
            user_id: User ID
            channel_name: Channel identifier
        """
        cache_key = WebSocketConnectionMonitor.get_connection_key(user_id, channel_name)

        connection_data = cache.get(cache_key)
        if connection_data:
            duration = time.time() - connection_data['connected_at']
            logger.info(
                f"[WS_MONITOR] User {user_id}: Connection unregistered "
                f"({channel_name}), duration: {duration:.1f}s"
            )

        cache.delete(cache_key)

    @staticmethod
    def get_connection_info(user_id, channel_name):
        """
        Get detailed connection information.

        Args:
            user_id: User ID
            channel_name: Channel identifier

        Returns:
            dict or None: Connection data if exists
        """
        cache_key = WebSocketConnectionMonitor.get_connection_key(user_id, channel_name)
        return cache.get(cache_key)
