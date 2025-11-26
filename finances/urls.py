# finances/urls.py

from django.urls import path
from . import views
from finances.views import views_password_reset

urlpatterns = [
    # === SETUP (must be first) ===
    path('setup/', views.initial_setup_view, name='initial_setup'),
    
    # === EXISTING ROUTES ===
    # General
    path('', views.dashboard_view, name='dashboard'),
    path('settings/', views.configuration_view, name='configuration'),
    path('auth/logout/', views.logout_view, name='auth_logout'),
    path('auth/logged-out/', views.logout_success_view, name='logout_success'),
    
    # User Profile
    path('profile/', views.user_profile_view, name='user_profile'),
    
    # Members (integrated into Settings page - configurations.html)
    path('members/', views.members_view, name='members'),  # Redirects to Settings for backward compatibility
    path('members/add/', views.add_member_view, name='member_add'),
    path('members/edit/<int:member_id>/', views.edit_member_view, name='member_edit'),
    path('members/remove/<int:member_id>/', views.remove_member_view, name='member_remove'), 
    
    # Investments
    path('investments/', views.investments_view, name='investments'), 
    path('investments/add/', views.investment_add_view, name='investment_add'),    

    # Flow Group
    path('flow-group/new/', views.create_flow_group_view, name='add_flow_group'), 
    path('flow-group/<int:group_id>/edit/', views.edit_flow_group_view, name='edit_flow_group'),
    path('flow-group/<int:group_id>/delete/', views.delete_flow_group_view, name='delete_flow_group'),
    
    # Income/Receipts
    path('receipt/new/', views.add_receipt_view, name='add_receipt'),

    # ==== Ajax routes ====
    # Used for both Expense Group items and Income items
    path('api/flow-group/item/save/', views.save_flow_item_ajax, name='save_flow_item_ajax'),
    path('api/flow-group/item/delete/', views.delete_flow_item_ajax, name='delete_flow_item_ajax'),
    path('api/flow-group/item/reorder/', views.reorder_flow_items_ajax, name='reorder_flow_items_ajax'),

    # Toggle Kids group realized status
    path('api/kids-group/toggle-realized/', views.toggle_kids_group_realized_ajax, name='toggle_kids_group_realized_ajax'),

    # Get available periods for dropdown
    path('api/periods/', views.get_periods_ajax, name='get_periods_ajax'),
    
    # Copy previous period data
    path('api/period/copy-previous/', views.copy_previous_period_ajax, name='copy_previous_period_ajax'),
    path('api/period/check-empty/', views.check_period_empty_ajax, name='check_period_empty_ajax'),

    # Create and validate periods
    path('api/period/validate-overlap/', views.validate_period_overlap_ajax, name='validate_period_overlap_ajax'),
    path('api/period/create/', views.create_period_ajax, name='create_period_ajax'),
    path('api/period/details/', views.get_period_details_ajax, name='get_period_details_ajax'),
    path('api/period/delete/', views.delete_period_ajax, name='delete_period_ajax'),
    
    # Reorder items at the dashboard
    path('ajax/reorder-flow-groups/', views.reorder_flow_groups_ajax, name='reorder_flow_groups_ajax'),

    # Bank Reconciliation
    path('bank-reconciliation/', views.bank_reconciliation_view, name='bank_reconciliation'),
    path('api/bank-balance/save/', views.save_bank_balance_ajax, name='save_bank_balance_ajax'),
    path('api/bank-balance/delete/', views.delete_bank_balance_ajax, name='delete_bank_balance_ajax'),

    # Updates and git updates
    path('check-updates/', views.check_for_updates, name='check_updates'),
    path('check-updates/manual/', views.manual_check_updates, name='manual_check_updates'),
    path('apply-local-updates/', views.apply_local_updates, name='apply_local_updates'),
    path('download-github-update/', views.download_github_update, name='download_github_update'),
    path('create-backup/', views.create_backup, name='create_backup'),
    path('download-backup/<str:filename>/', views.download_backup, name='download_backup'),
    path('restore-backup/', views.restore_backup, name='restore_backup'),
    path('skip-updates/', views.skip_updates, name='skip_updates'),

    #Notifications
    path('api/notifications/', views.get_notifications_ajax, name='get_notifications_ajax'),
    path('api/notifications/acknowledge/', views.acknowledge_notification_ajax, name='acknowledge_notification_ajax'),
    path('api/notifications/acknowledge-all/', views.acknowledge_all_notifications_ajax, name='acknowledge_all_notifications_ajax'),

    # Admin warning
    path('mark-admin-warning-seen/', views.mark_admin_warning_seen, name='mark_admin_warning_seen'),

    # Password Reset
    path('password-reset/', views_password_reset.password_reset_request, name='password_reset_request'),
    path('password-reset/verify/', views_password_reset.password_reset_verify, name='password_reset_verify'),
    path('password-reset/confirm/', views_password_reset.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/resend/', views_password_reset.password_reset_resend_code, name='password_reset_resend'),
]


