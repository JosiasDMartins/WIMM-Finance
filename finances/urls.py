# finances/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # General
    path('', views.dashboard_view, name='dashboard'),
    path('settings/', views.configuration_view, name='configuration'),
    path('auth/logout/', views.logout_view, name='auth_logout'),
    path('auth/logged-out/', views.logout_success_view, name='logout_success'),
    
    # User Profile
    path('profile/', views.user_profile_view, name='user_profile'),
    
    # Members
    path('members/', views.members_view, name='members'),
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

    # Toggle Kids group realized status
    path('api/kids-group/toggle-realized/', views.toggle_kids_group_realized_ajax, name='toggle_kids_group_realized_ajax'),

    # Get available periods for dropdown
    path('api/periods/', views.get_periods_ajax, name='get_periods_ajax'),
]
