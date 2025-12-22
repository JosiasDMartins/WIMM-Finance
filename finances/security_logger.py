"""
Security Event Logging Module

Provides configurable security event logging with multiple detail levels.
All security-related events (WebSocket connections, rate limits, XSS attempts, etc.)
are logged through this module.

Log Levels:
- 0: Disabled - No security logging
- 1: Basic - Only critical security events (violations, attacks)
- 2: Standard - Normal security events (connections, disconnections, violations)
- 3: Detailed - All security events with full context and debugging info
"""

import logging
from django.conf import settings
from typing import Optional, Dict, Any

# Get logger for security events
logger = logging.getLogger('security')


class SecurityLogger:
    """
    Centralized security logging with configurable detail levels.

    Usage:
        SecurityLogger.log_connection(user_id, username, client_ip)
        SecurityLogger.log_rate_limit_violation(user_id, attempts)
        SecurityLogger.log_xss_attempt(content)
    """

    @staticmethod
    def get_log_level() -> int:
        """
        Get current security log level from settings.

        Returns:
            int: Log level (0=disabled, 1=basic, 2=standard, 3=detailed)
        """
        return getattr(settings, 'SECURITY_LOG_LEVEL', 0)

    @staticmethod
    def is_enabled(min_level: int = 1) -> bool:
        """
        Check if security logging is enabled at given level.

        Args:
            min_level: Minimum level required to log this event

        Returns:
            bool: True if logging is enabled at this level
        """
        return SecurityLogger.get_log_level() >= min_level

    # ========================================================================
    # WebSocket Connection Events
    # ========================================================================

    @staticmethod
    def log_connection_attempt(user_id: int, username: str, client_ip: str = 'unknown'):
        """
        Log WebSocket connection attempt.

        Level 2 (Standard): Logs successful connections
        Level 3 (Detailed): Includes client IP and full context

        Examples:
            Level 2: [WS_CONNECT] User 5 (john) connected
            Level 3: [WS_CONNECT] User 5 (john) connected from 192.168.1.100
        """
        if SecurityLogger.is_enabled(2):
            if SecurityLogger.get_log_level() >= 3:
                logger.info(
                    f"[WS_CONNECT] User {user_id} ({username}) connected from {client_ip}"
                )
            else:
                logger.info(
                    f"[WS_CONNECT] User {user_id} ({username}) connected"
                )

    @staticmethod
    def log_connection_rejected(reason: str, user_id: Optional[int] = None, client_ip: str = 'unknown'):
        """
        Log rejected WebSocket connection.

        Level 1 (Basic): Logs all rejections (security relevant)
        Level 3 (Detailed): Includes full context

        Examples:
            Level 1: [WS_REJECT] Connection rejected: unauthenticated
            Level 3: [WS_REJECT] Connection rejected: unauthenticated - User None from 192.168.1.100
        """
        if SecurityLogger.is_enabled(1):
            if SecurityLogger.get_log_level() >= 3 and user_id:
                logger.warning(
                    f"[WS_REJECT] Connection rejected: {reason} - User {user_id} from {client_ip}"
                )
            else:
                logger.warning(
                    f"[WS_REJECT] Connection rejected: {reason}"
                )

    @staticmethod
    def log_disconnection(user_id: int, username: str, close_code: int, duration: Optional[float] = None):
        """
        Log WebSocket disconnection.

        Level 3 (Detailed): Logs all disconnections with duration

        Examples:
            Level 3: [WS_DISCONNECT] User 5 (john) disconnected - Code: 1000, Duration: 3600.5s
        """
        if SecurityLogger.is_enabled(3):
            if duration is not None:
                logger.info(
                    f"[WS_DISCONNECT] User {user_id} ({username}) disconnected - "
                    f"Code: {close_code}, Duration: {duration:.1f}s"
                )
            else:
                logger.info(
                    f"[WS_DISCONNECT] User {user_id} ({username}) disconnected - Code: {close_code}"
                )

    # ========================================================================
    # Rate Limiting Events
    # ========================================================================

    @staticmethod
    def log_rate_limit_violation(user_id: int, attempts: int, max_attempts: int, retry_after: int):
        """
        Log rate limit violation.

        Level 1 (Basic): Always logged (potential attack)

        Examples:
            Level 1: [RATE_LIMIT] User 5 exceeded limit: 10/10 attempts - Retry after 45s
        """
        if SecurityLogger.is_enabled(1):
            logger.warning(
                f"[RATE_LIMIT] User {user_id} exceeded limit: {attempts}/{max_attempts} attempts - "
                f"Retry after {retry_after}s"
            )

    @staticmethod
    def log_rate_limit_reset(user_id: int):
        """
        Log rate limit reset.

        Level 3 (Detailed): Log administrative resets

        Examples:
            Level 3: [RATE_LIMIT] User 5 rate limit manually reset
        """
        if SecurityLogger.is_enabled(3):
            logger.info(f"[RATE_LIMIT] User {user_id} rate limit manually reset")

    # ========================================================================
    # Connection Health Events
    # ========================================================================

    @staticmethod
    def log_heartbeat_failure(user_id: int, channel_name: str, time_since_last: float):
        """
        Log heartbeat failure (stale connection).

        Level 2 (Standard): Log unhealthy connections

        Examples:
            Level 2: [HEARTBEAT] User 5 connection unhealthy - 95.3s since last heartbeat
        """
        if SecurityLogger.is_enabled(2):
            logger.warning(
                f"[HEARTBEAT] User {user_id} connection unhealthy - "
                f"{time_since_last:.1f}s since last heartbeat"
            )

    # ========================================================================
    # XSS Prevention Events
    # ========================================================================

    @staticmethod
    def log_xss_attempt(content: str, event_type: str = 'unknown'):
        """
        Log potential XSS attempt detected.

        Level 1 (Basic): Always logged (attack attempt)
        Level 3 (Detailed): Includes sanitized content sample

        Examples:
            Level 1: [XSS_BLOCKED] Potential XSS detected in broadcast
            Level 3: [XSS_BLOCKED] Potential XSS in transaction_created: <script>alert...
        """
        if SecurityLogger.is_enabled(1):
            if SecurityLogger.get_log_level() >= 3:
                # Show first 100 chars of malicious content
                sample = content[:100] + '...' if len(content) > 100 else content
                logger.warning(
                    f"[XSS_BLOCKED] Potential XSS in {event_type}: {sample}"
                )
            else:
                logger.warning(
                    f"[XSS_BLOCKED] Potential XSS detected in {event_type}"
                )

    @staticmethod
    def log_sanitization(event_type: str, fields_sanitized: int):
        """
        Log data sanitization event.

        Level 3 (Detailed): Log all sanitizations

        Examples:
            Level 3: [SANITIZE] Broadcast transaction_created: 3 fields sanitized
        """
        if SecurityLogger.is_enabled(3):
            logger.debug(
                f"[SANITIZE] Broadcast {event_type}: {fields_sanitized} fields sanitized"
            )

    # ========================================================================
    # Authentication Events
    # ========================================================================

    @staticmethod
    def log_auth_failure(username: str, reason: str, client_ip: str = 'unknown'):
        """
        Log authentication failure.

        Level 1 (Basic): Always logged (security relevant)
        Level 3 (Detailed): Includes client IP

        Examples:
            Level 1: [AUTH_FAIL] Failed login for user: john - Invalid password
            Level 3: [AUTH_FAIL] Failed login for user: john from 192.168.1.100 - Invalid password
        """
        if SecurityLogger.is_enabled(1):
            if SecurityLogger.get_log_level() >= 3:
                logger.warning(
                    f"[AUTH_FAIL] Failed login for user: {username} from {client_ip} - {reason}"
                )
            else:
                logger.warning(
                    f"[AUTH_FAIL] Failed login for user: {username} - {reason}"
                )

    # ========================================================================
    # Broadcast Data Validation
    # ========================================================================

    @staticmethod
    def log_invalid_broadcast(event_type: str, reason: str, data_sample: Optional[Dict[str, Any]] = None):
        """
        Log invalid broadcast data.

        Level 1 (Basic): Always logged (data integrity issue)
        Level 3 (Detailed): Includes data sample

        Examples:
            Level 1: [BROADCAST_INVALID] transaction_created failed validation: missing required fields
            Level 3: [BROADCAST_INVALID] transaction_created: missing required fields - Data: {'id': 5}
        """
        if SecurityLogger.is_enabled(1):
            if SecurityLogger.get_log_level() >= 3 and data_sample:
                logger.error(
                    f"[BROADCAST_INVALID] {event_type}: {reason} - Data: {data_sample}"
                )
            else:
                logger.error(
                    f"[BROADCAST_INVALID] {event_type} failed validation: {reason}"
                )

    # ========================================================================
    # Generic Security Events
    # ========================================================================

    @staticmethod
    def log_security_event(event_type: str, message: str, level: int = 2, severity: str = 'info'):
        """
        Log generic security event.

        Args:
            event_type: Type of security event
            message: Event message
            level: Minimum log level required (1=basic, 2=standard, 3=detailed)
            severity: Log severity (info, warning, error, critical)

        Examples:
            SecurityLogger.log_security_event('CUSTOM', 'Custom event occurred', level=2)
        """
        if SecurityLogger.is_enabled(level):
            log_func = getattr(logger, severity, logger.info)
            log_func(f"[{event_type}] {message}")


# Convenience functions for quick logging
def log_ws_connection(user_id: int, username: str, client_ip: str = 'unknown'):
    """Shortcut for logging WebSocket connection."""
    SecurityLogger.log_connection_attempt(user_id, username, client_ip)


def log_ws_rejection(reason: str, user_id: Optional[int] = None, client_ip: str = 'unknown'):
    """Shortcut for logging WebSocket rejection."""
    SecurityLogger.log_connection_rejected(reason, user_id, client_ip)


def log_rate_limit(user_id: int, attempts: int, max_attempts: int, retry_after: int):
    """Shortcut for logging rate limit violation."""
    SecurityLogger.log_rate_limit_violation(user_id, attempts, max_attempts, retry_after)


def log_xss(content: str, event_type: str = 'unknown'):
    """Shortcut for logging XSS attempt."""
    SecurityLogger.log_xss_attempt(content, event_type)
