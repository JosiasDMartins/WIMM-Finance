# finances/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max # FIX: Ensure Max is imported
from django.db import transaction as db_transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST 
from django.contrib.auth import get_user_model 

from .models import Investment # Certifique-se de que Investment está importado

from .models import FamilyMember, CustomUser # <-- Garanta que CustomUser está importado
from .forms import AddMemberForm # <-- Garanta que AddMemberForm está importado


from .models import (
    Family, FamilyMember, FamilyConfiguration, 
    FlowGroup, Transaction, Investment, FlowGroupAccess, CustomUser
)
# from .forms import ... # Assuming forms will be added later
from django.utils import timezone
import json
from datetime import datetime

# --- Utility Function to get Family Context ---
def get_family_context(user):
    """Retrieves the Family and FamilyMember context for the logged-in user."""
    try:
        family_member = FamilyMember.objects.get(user=user)
        family = family_member.family
        # Get all members in the family for dropdowns
        all_family_members = FamilyMember.objects.filter(family=family).select_related('user').order_by('user__username')
        return family, family_member, all_family_members
    except FamilyMember.DoesNotExist:
        return None, None, []


# --- Core Views ---

@login_required
def dashboard_view(request):
    # 1. Get the current user's Family context
    family, family_member, _ = get_family_context(request.user)
    
    if not family:
        # Handle case where user is not yet assigned to a family
        return render(request, 'finances/setup.html') 

    # --- Period setup (simplified, you'll need a proper date range calculation) ---
    import datetime
    today = datetime.date.today()
    start_date = today.replace(day=1)
    end_date = today

    # --- 2. Fetch Flow Groups ---
    all_groups = FlowGroup.objects.filter(family=family)
    expense_groups_query = all_groups.filter(group_type__in=['EXPENSE_MAIN', 'EXPENSE_SECONDARY'])
    income_groups_query = all_groups.filter(group_type='INCOME')

    # --- 3. Calculate Totals (Simplified: Budgeted vs. Actual) ---
    expense_groups_with_spent = []
    total_realized_expense = 0
    for group in expense_groups_query:
        spent_amount = Transaction.objects.filter(
            flow_group=group, 
            date__gte=start_date, 
            date__lte=end_date
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        group.total_spent = spent_amount
        expense_groups_with_spent.append(group)
        total_realized_expense += spent_amount

    total_budgeted_expense = expense_groups_query.aggregate(Sum('budgeted_amount'))['budgeted_amount__sum'] or 0
    total_budgeted_income = income_groups_query.aggregate(Sum('budgeted_amount'))['budgeted_amount__sum'] or 0

    income_group_ids = income_groups_query.values_list('id', flat=True)
    recent_income_transactions = Transaction.objects.filter(
        flow_group__in=income_group_ids,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('-date')

    total_realized_income = recent_income_transactions.aggregate(Sum('amount'))['amount__sum'] or 0

    # --- 4. Final Balance Sheet Calculations ---
    summary_totals = {
        'total_budgeted_income': total_budgeted_income,
        'total_realized_income': total_realized_income,
        'total_budgeted_expense': total_budgeted_expense,
        'total_realized_expense': total_realized_expense,
        'estimated_result': (total_budgeted_income or 0) - (total_budgeted_expense or 0),
        'realized_result': (total_realized_income or 0) - (total_realized_expense or 0),
    }

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'expense_groups': expense_groups_with_spent,
        'recent_income_transactions': recent_income_transactions,
        'summary_totals': summary_totals,
        'current_member': family_member, 
    }
    
    return render(request, 'finances/Dashboard.html', context)


@login_required
def create_flow_group_view(request):
    """Handles displaying the form (GET) and creating a new FlowGroup (POST)."""
    
    family, current_member, family_members = get_family_context(request.user)
    error_message = None

    if not family:
        return redirect('setup_family') 

    # --- POST: Handling Form Submission (Creation) ---
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            budgeted_amount = request.POST.get('budgeted_amount')
            group_type = request.POST.get('group_type')
            # Checkbox: if present, value is 'on'. If not, it's None.
            is_shared = request.POST.get('is_shared') == 'on' 

            if not all([name, budgeted_amount]):
                raise ValueError("Group Name and Budgeted Amount are required.")
            
            # Create the FlowGroup
            new_group = FlowGroup.objects.create(
                name=name,
                budgeted_amount=budgeted_amount,
                group_type=group_type or 'EXPENSE_MAIN',
                family=family,
                owner=request.user,
                is_shared=is_shared
            )
            
            # Redirect to the Edit page of the newly created group
            return redirect('edit_flow_group', group_id=new_group.id) 

        except Exception as e:
            error_message = f"Error saving group: {e}"
            # Continue to re-render the form with error

    # --- GET: Displaying Form (Creation) ---
    context = {
        'flow_group': None, 
        'transactions': [],
        'family_members': family_members, 
        'current_member': current_member,
        'group_types': FlowGroup.GROUP_TYPES,
        'error_message': error_message,
    }
    
    # Uses the FlowGroup.html for creation
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def edit_flow_group_view(request, group_id):
    """Loads the GroupFlow screen with all data for editing or handles POST update."""
    
    family, current_member, family_members = get_family_context(request.user)

    if not family:
        return redirect('setup_family') 

    flow_group = get_object_or_404(FlowGroup, id=group_id, family=family)
    
    # --- POST: Handling Form Submission (Update) ---
    if request.method == 'POST':
        try:
            flow_group.name = request.POST.get('name')
            flow_group.budgeted_amount = request.POST.get('budgeted_amount')
            flow_group.group_type = request.POST.get('group_type')
            flow_group.is_shared = request.POST.get('is_shared') == 'on'
            
            flow_group.save()
            return redirect('edit_flow_group', group_id=flow_group.id) 

        except Exception as e:
            error_message = f"Error updating group: {e}"
            # The code continues to re-render the form with error

    # Security check: Ensure user belongs to the family AND the flow group belongs to the family
    if flow_group.family != current_member.family:
        return HttpResponseForbidden("Access denied.")

    # Fetch all transactions ordered by the 'order' field
    transactions = flow_group.transactions.all().select_related('member', 'member__user')

    context = {
        'flow_group': flow_group,
        'transactions': transactions,
        'family_members': family_members, 
        'current_member': current_member, 
        'group_types': FlowGroup.GROUP_TYPES,
        'error_message': None, # Update error handling if POST failed
    }

    return render(request, 'finances/FlowGroup.html', context)




# --- Placeholder Views ---
@login_required
def configuration_view(request):
    """ Placeholder for Configuration.html """
    return HttpResponse("<h1>Configuration Page (in development)</h1>")

@login_required
def add_receipt_view(request):
    """ Placeholder for Add Receipt/Income. """
    return HttpResponse("<h1>Adicionar Nova Receita / Entrada (in development)</h1>")

@login_required
def investments_view(request):
    """
    Exibe a tela de Investimentos.
    Busca todos os investimentos da família do usuário logado.
    """
    family, current_member, family_members = get_family_context(request.user)

    if not family:
        # Se não tiver família, redireciona para alguma tela de setup ou dashboard
        return redirect('dashboard') # Ou 'setup_family' se você tiver uma

    # Busca todos os investimentos associados à família
    # NOTE: O modelo Investment precisa de um ForeignKey para Family
    # Baseado no seu models.py, o Investment tem 'family = models.ForeignKey(Family, ...)'
    all_investments = Investment.objects.filter(family=family).order_by('name')

    # TODO: No futuro, adicione lógica para buscar cotações em tempo real

    context = {
        'all_investments': all_investments,
        'current_member': current_member,
        # Adicione outros dados relevantes se necessário
    }
    
    # O Django irá procurar por 'finances/invest.html'
    return render(request, 'finances/invest.html', context)

@login_required
def add_investment_view(request):
    """
    View que irá processar a adição de um novo investimento. 
    Por enquanto, é um placeholder que redireciona de volta.
    """
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    # TODO: No futuro, você implementará o formulário InvestmentForm e a lógica de salvamento aqui.
    
    # Por agora, apenas redirecionamos de volta para a lista de investimentos após a tentativa de acesso.
    return redirect('investments')

@login_required
def members_view(request):
    """
    Exibe a lista de membros da família.
    """
    family, current_member, all_family_members = get_family_context(request.user)

    if not family:
        return redirect('dashboard')

    # Cria um formulário limpo para a renderização inicial
    add_member_form = AddMemberForm() 
    
    context = {
        'current_member': current_member,
        'family_members': all_family_members,
        'add_member_form': add_member_form, # Passa o formulário
        'is_admin': current_member.role == 'ADMIN', 
    }
    
    return render(request, 'finances/Members.html', context)


@login_required
@db_transaction.atomic 
def add_member_view(request):
    """
    Cria um novo CustomUser e o associa à família como FamilyMember.
    """
    # 1. Correção do NameError: get_user_model precisa ser importado ou definido.
    # Assumimos que foi importado no topo do arquivo.
    family, current_member, all_family_members = get_family_context(request.user)
    UserModel = get_user_model() # Agora deve funcionar

    if not current_member or current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Acesso negado. Apenas administradores/pais podem adicionar membros.")

    if request.method == 'POST':
        form = AddMemberForm(request.POST) 
        
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email'] # Campo adicionado
            password = form.cleaned_data['password']
            role = form.cleaned_data['role']
            
            # 2. Cria o novo CustomUser (passando email, que pode ser vazio)
            new_user = UserModel.objects.create_user(
                username=username,
                email=email, # Passa o e-mail, se existir
                password=password,
            )
            
            # 3. Associa o novo usuário à família
            FamilyMember.objects.create(
                user=new_user, 
                family=family, 
                role=role
            )
            
            return redirect('members')
        
        # 4. Se o formulário for inválido:
        context = {
            'current_member': current_member,
            'family_members': all_family_members,
            'add_member_form': form, # Passa o formulário com erros de volta
            'is_admin': current_member.role == 'ADMIN', 
        }
        # Renderiza a página de membros para exibir os erros.
        return render(request, 'finances/Members.html', context)
    
    return redirect('members')


@login_required
@db_transaction.atomic
def remove_member_view(request, member_id):
    """
    Remove um FamilyMember e o CustomUser associado.
    Requer que o usuário logado seja ADMIN/PARENT e não esteja tentando se excluir.
    """
    # 1. Obter o FamilyMember a ser excluído
    try:
        member_to_remove = FamilyMember.objects.select_related('user', 'family').get(id=member_id)
        user_to_remove = member_to_remove.user
        
    except FamilyMember.DoesNotExist:
        # Se o membro não existe, apenas redireciona (ou mostra um erro)
        return redirect('members')

    # 2. Obter o contexto do usuário logado
    family, current_member, _ = get_family_context(request.user)

    # 3. Verificações de Segurança
    
    # A) Permissão: Apenas ADMIN ou PARENT podem excluir
    if not current_member or current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Acesso negado. Apenas administradores/pais podem remover membros.")
    
    # B) Não permitir auto-exclusão
    if member_to_remove.user == request.user:
        messages.error(request, "Você não pode remover a si mesmo da família.")
        return redirect('members')
        
    # C) Pertencimento à Família: O membro a ser removido deve pertencer à família do usuário logado
    if member_to_remove.family != family:
        return HttpResponseForbidden("Acesso negado. Membro não pertence à sua família.")

    
    # 4. Executar a Exclusão
    
    # Primeiro, excluímos o FamilyMember
    member_to_remove.delete()
    
    # Em seguida, excluímos o CustomUser.
    # Isso é crucial para que a conta não possa mais fazer login.
    user_to_remove.delete()
    
    # 5. Mensagem e Redirecionamento de Sucesso
    # Se você tiver mensagens no Django (django.contrib.messages)
    # messages.success(request, f"O membro '{user_to_remove.username}' foi removido com sucesso.")
    
    return redirect('members')

# --- AJAX Views ---

@login_required
@require_POST
@db_transaction.atomic
def save_flow_item_ajax(request):
    """Handles AJAX request to create or update a single Transaction item."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")

    try:
        data = json.loads(request.body)
        
        flow_group_id = data.get('flow_group_id')
        description = data.get('description')
        amount = data.get('amount')
        date_str = data.get('date')
        member_id = data.get('member_id')
        transaction_id = data.get('transaction_id')

        # Input validation
        if not all([flow_group_id, description, amount, date_str, member_id]):
            return JsonResponse({'error': 'Missing required fields.'}, status=400)

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id)
        member = get_object_or_404(FamilyMember, id=member_id)
        current_member = get_object_or_404(FamilyMember, user=request.user)

        if flow_group.family != current_member.family or member.family != current_member.family:
            return JsonResponse({'error': 'Access denied.'}, status=403)
        
        amount = float(amount)
        item_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if transaction_id:
            transaction = get_object_or_404(Transaction, id=transaction_id, flow_group=flow_group)
            transaction.description = description
            transaction.amount = amount
            transaction.date = item_date
            transaction.member = member
            transaction.save()
            action = 'updated'
        else:
            # Create new transaction
            max_order = Transaction.objects.filter(flow_group=flow_group).aggregate(max_order=Max('order'))['max_order'] or -1
            new_order = max_order + 1

            transaction = Transaction.objects.create(
                flow_group=flow_group,
                description=description,
                amount=amount,
                date=item_date,
                member=member,
                order=new_order
            )
            action = 'created'
            
        # Refetch member data for name
        member_name = FamilyMember.objects.get(id=member_id).user.username

        return JsonResponse({
            'status': 'success',
            'action': action,
            'transaction_id': transaction.id,
            'description': transaction.description,
            'amount': amount,
            'member_name': member_name, # Use the refetched name
            'date': transaction.date.strftime('%Y-%m-%d')
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def delete_flow_item_ajax(request):
    """Handles AJAX request to delete a single Transaction item."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return JsonResponse({'error': 'Missing transaction_id.'}, status=400)

        transaction = get_object_or_404(Transaction, id=transaction_id)
        current_member = get_object_or_404(FamilyMember, user=request.user)

        if transaction.flow_group.family != current_member.family:
            return JsonResponse({'error': 'Access denied. Transaction does not belong to your family.'}, status=403)
        
        transaction.delete()

        return JsonResponse({'status': 'success', 'transaction_id': transaction_id})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)