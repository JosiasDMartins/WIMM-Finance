# finances/urls.py (finances/urls.py)

from django.urls import path, include
from . import views

urlpatterns = [
    # Rotas existentes
    path('', views.dashboard_view, name='dashboard'),
    path('settings/', views.configuration_view, name='configuration'),
    
    path('members/', views.members_view, name='members'),
    path('members/add/', views.add_member_view, name='member_add'),
    path('members/remove/<int:member_id>/', views.remove_member_view, name='member_remove'), 
    
    # Rota para Investimentos (NOVA)
    path('investments/', views.investments_view, name='investments'), # <-- NOVA ROTA AQUI
    path('investments/add/', views.add_investment_view, name='investment_add'), # <-- CORRIGE O NoReverseMatch    

    # Rotas de Flow Group (Criação/Edição)
    path('flow-group/new/', views.create_flow_group_view, name='add_flow_group'), 
    path('flow-group/<int:group_id>/edit/', views.edit_flow_group_view, name='edit_flow_group'),
    
    # Rota para Adicionar Receita/Entrada
    path('receipt/new/', views.add_receipt_view, name='add_receipt'),

    # Rotas para AJAX (Flow Group Items)
    path('api/flow-group/item/save/', views.save_flow_item_ajax, name='save_flow_item_ajax'),
    path('api/flow-group/item/delete/', views.delete_flow_item_ajax, name='delete_flow_item_ajax'),    

    # ... Adicione outras rotas aqui (members, etc.)
]