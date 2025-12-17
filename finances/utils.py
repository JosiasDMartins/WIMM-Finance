"""
Backward compatibility module for finances.utils

This module maintains backward compatibility by re-exporting all utility functions
from the modularized utils package. All new code should import directly from
finances.utils.* submodules, but existing code using 'from finances.utils import X'
will continue to work.

Migration path:
    OLD: from finances.utils import get_current_period_dates
    NEW: from finances.utils.period_utils import get_current_period_dates
    or
    NEW: from finances.utils import get_current_period_dates (still works via this file)
"""

# Re-export all functions from the utils package for backward compatibility
from .utils import *  # noqa: F401, F403

# This ensures that all existing imports like:
#   from finances.utils import get_current_period_dates
# continue to work without any code changes
