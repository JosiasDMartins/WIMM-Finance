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

# Database backup utilities
from .db_backup import (
    create_database_backup,
)

# Database common utilities
from .db_utils_common import (
    get_database_engine,
    detect_backup_type,
)

# Database SQLite utilities
from .db_utils_sqlite import (
    restore_sqlite_from_file,
    create_sqlite_backup,
)

# Database PostgreSQL utilities
from .db_utils_pgsql import (
    restore_postgres_from_file,
    create_postgres_backup,
)

# Database migration utilities
from .db_data_migration import (
    check_and_migrate,
    should_migrate,
    migrate_sqlite_to_postgres,
)

# Database restore with migration
from .db_restore_migration import (
    restore_sqlite_backup_to_postgres,
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

    # Database backup utilities
    'create_database_backup',
    'create_sqlite_backup',
    'create_postgres_backup',

    # Database common utilities
    'get_database_engine',
    'detect_backup_type',

    # Database restore utilities
    'restore_sqlite_from_file',
    'restore_postgres_from_file',
    'restore_sqlite_backup_to_postgres',

    # Database migration utilities
    'check_and_migrate',
    'should_migrate',
    'migrate_sqlite_to_postgres',
]
