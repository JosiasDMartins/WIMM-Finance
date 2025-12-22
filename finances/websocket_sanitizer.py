"""
WebSocket Data Sanitization Module

Provides sanitization utilities for WebSocket broadcast data to prevent XSS attacks.
All user-generated content should be sanitized before broadcasting to prevent
injection of malicious HTML/JavaScript.
"""

import bleach
import logging
from typing import Any, Dict, List, Union
from finances.security_logger import SecurityLogger

logger = logging.getLogger(__name__)


class WebSocketSanitizer:
    """
    Sanitizer for WebSocket broadcast data.

    Uses bleach library to strip ALL HTML tags from user-provided content.
    This ensures that malicious scripts cannot be injected via WebSocket messages.
    """

    # Allowed tags (NONE - we strip all HTML for maximum security)
    # If you need to allow specific tags in the future, add them here
    ALLOWED_TAGS = []

    # Allowed attributes (NONE)
    ALLOWED_ATTRIBUTES = {}

    # Allowed CSS properties (NONE)
    ALLOWED_STYLES = []

    @staticmethod
    def sanitize_string(value: str) -> str:
        """
        Sanitize a single string value.

        Strips ALL HTML tags and attributes to prevent XSS.

        Args:
            value: String to sanitize

        Returns:
            str: Sanitized string (all HTML removed)
        """
        if not isinstance(value, str):
            return value

        # Strip all HTML tags
        cleaned = bleach.clean(
            value,
            tags=WebSocketSanitizer.ALLOWED_TAGS,
            attributes=WebSocketSanitizer.ALLOWED_ATTRIBUTES,
            styles=WebSocketSanitizer.ALLOWED_STYLES,
            strip=True  # Remove tags completely instead of escaping
        )

        # Additional safety: ensure no script tags survived
        if '<script' in cleaned.lower() or 'javascript:' in cleaned.lower():
            logger.warning(f"[WS_SANITIZER] Potential XSS detected and blocked: {value[:100]}")
            SecurityLogger.log_xss_attempt(value, 'websocket_broadcast')
            # Replace with safe placeholder
            cleaned = "[BLOCKED: Potential XSS]"

        return cleaned

    @staticmethod
    def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize all string values in a dictionary.

        Args:
            data: Dictionary to sanitize

        Returns:
            dict: Sanitized dictionary
        """
        sanitized = {}

        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = WebSocketSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = WebSocketSanitizer.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = WebSocketSanitizer.sanitize_list(value)
            else:
                # Numbers, booleans, None, etc. - pass through unchanged
                sanitized[key] = value

        return sanitized

    @staticmethod
    def sanitize_list(data: List[Any]) -> List[Any]:
        """
        Recursively sanitize all string values in a list.

        Args:
            data: List to sanitize

        Returns:
            list: Sanitized list
        """
        sanitized = []

        for item in data:
            if isinstance(item, str):
                sanitized.append(WebSocketSanitizer.sanitize_string(item))
            elif isinstance(item, dict):
                sanitized.append(WebSocketSanitizer.sanitize_dict(item))
            elif isinstance(item, list):
                sanitized.append(WebSocketSanitizer.sanitize_list(item))
            else:
                sanitized.append(item)

        return sanitized

    @staticmethod
    def sanitize_for_broadcast(data: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
        """
        Main sanitization function for WebSocket broadcasts.

        Sanitizes any data structure (dict, list, string) recursively.

        Args:
            data: Data to sanitize (can be dict, list, string, or primitive)

        Returns:
            Sanitized data in the same structure

        Example:
            >>> data = {
            ...     'type': 'transaction_created',
            ...     'transaction': {
            ...         'description': 'Lunch at <script>alert("XSS")</script> cafe',
            ...         'amount': 25.50
            ...     }
            ... }
            >>> sanitized = WebSocketSanitizer.sanitize_for_broadcast(data)
            >>> print(sanitized['transaction']['description'])
            'Lunch at  cafe'  # Script tag removed
        """
        if isinstance(data, dict):
            return WebSocketSanitizer.sanitize_dict(data)
        elif isinstance(data, list):
            return WebSocketSanitizer.sanitize_list(data)
        elif isinstance(data, str):
            return WebSocketSanitizer.sanitize_string(data)
        else:
            # Primitive types (int, float, bool, None) - pass through
            return data


def sanitize_broadcast_data(data: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
    """
    Convenience function for sanitizing WebSocket broadcast data.

    This is the main function that should be called before broadcasting
    any user-generated content via WebSocket.

    Args:
        data: Data to sanitize

    Returns:
        Sanitized data

    Example:
        from finances.websocket_sanitizer import sanitize_broadcast_data
        from finances.websocket_utils import WebSocketBroadcaster

        # Sanitize before broadcasting
        safe_data = sanitize_broadcast_data({
            'type': 'notification',
            'message': user_input  # Potentially dangerous
        })

        WebSocketBroadcaster.broadcast_to_family(family_id, safe_data)
    """
    return WebSocketSanitizer.sanitize_for_broadcast(data)
