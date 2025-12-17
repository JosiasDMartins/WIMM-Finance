"""
Utility functions for SweetMoney application.

This package contains reusable utility functions used across the application,
organized by functional area.
"""

# Period utilities
from .period_utils import (
    get_current_period_dates,
    calculate_period_for_date,
    check_period_change_impact,
    get_available_periods,
    current_period_has_data,
    close_current_period,
)

# Currency utilities
from .currency_utils import (
    get_period_currency,
    ensure_period_exists,
)

# FlowGroup utilities
from .flowgroup_utils import (
    copy_previous_period_data,
    apply_period_configuration_change,
)

# Permission utilities
from .permission_utils import (
    user_can_access_flow_group,
)

# Role history utilities
from .role_history_utils import (
    get_member_role_for_period,
    save_role_history_if_changed,
)

# Database restore utilities
from .db_restore import (
    restore_database_from_file,
)

__all__ = [
    # Period utilities
    'get_current_period_dates',
    'calculate_period_for_date',
    'check_period_change_impact',
    'get_available_periods',
    'current_period_has_data',
    'close_current_period',

    # Currency utilities
    'get_period_currency',
    'ensure_period_exists',

    # FlowGroup utilities
    'copy_previous_period_data',
    'apply_period_configuration_change',

    # Permission utilities
    'user_can_access_flow_group',

    # Role history utilities
    'get_member_role_for_period',
    'save_role_history_if_changed',

    # Database restore utilities
    'restore_database_from_file',
]
