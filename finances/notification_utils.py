# finances/notification_utils.py

from django.utils import timezone
from django.urls import reverse
from decimal import Decimal


def create_overdue_notifications(family, member):
    """
    Cria notificações para transações vencidas (realized=False e data passada).
    Não cria duplicatas para transações já notificadas.
    """
    from .models import Transaction, Notification, FlowGroup
    
    today = timezone.localdate()
    
    # Busca transações não realizadas e vencidas
    overdue_transactions = Transaction.objects.filter(
        flow_group__family=family,
        realized=False,
        date__lt=today
    ).select_related('flow_group', 'member')
    
    # Filtrar por permissões do membro
    accessible_flow_groups = get_accessible_flow_groups(family, member)
    overdue_transactions = overdue_transactions.filter(flow_group__in=accessible_flow_groups)
    
    notifications_created = 0
    
    for transaction in overdue_transactions:
        # Verifica se já existe notificação não reconhecida para esta transação
        existing = Notification.objects.filter(
            member=member,
            transaction=transaction,
            notification_type='OVERDUE',
            is_acknowledged=False
        ).exists()
        
        if not existing:
            days_overdue = (today - transaction.date).days
            message = f"Transaction '{transaction.description}' is {days_overdue} day{'s' if days_overdue > 1 else ''} overdue"
            
            # URL para o FlowGroup
            target_url = reverse('edit_flow_group', kwargs={'group_id': transaction.flow_group.id}) + f"?period={transaction.flow_group.period_start_date.strftime('%Y-%m-%d')}"
            
            Notification.objects.create(
                family=family,
                member=member,
                notification_type='OVERDUE',
                transaction=transaction,
                flow_group=transaction.flow_group,
                message=message,
                target_url=target_url
            )
            notifications_created += 1
    
    return notifications_created


def create_overbudget_notifications(family, member):
    """
    Cria notificações para FlowGroups que excederam o orçamento.
    """
    from .models import FlowGroup, Notification
    from django.db.models import Sum, Q
    
    # Busca FlowGroups acessíveis ao membro
    accessible_flow_groups = get_accessible_flow_groups(family, member)
    
    # Filtra apenas FlowGroups de despesa (EXPENSE_MAIN e EXPENSE_SECONDARY)
    expense_groups = accessible_flow_groups.filter(
        Q(group_type='EXPENSE_MAIN') | Q(group_type='EXPENSE_SECONDARY')
    )
    
    notifications_created = 0
    
    for flow_group in expense_groups:
        # Calcula total realizado
        realized_total = flow_group.transactions.filter(realized=True).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        budgeted = flow_group.budgeted_amount.amount if hasattr(flow_group.budgeted_amount, 'amount') else flow_group.budgeted_amount
        
        # Verifica se está acima do orçamento
        if realized_total > budgeted:
            # Verifica se já existe notificação não reconhecida
            existing = Notification.objects.filter(
                member=member,
                flow_group=flow_group,
                notification_type='OVERBUDGET',
                is_acknowledged=False
            ).exists()
            
            if not existing:
                over_amount = realized_total - budgeted
                message = f"'{flow_group.name}' is over budget by {over_amount:.2f}"
                
                target_url = reverse('edit_flow_group', kwargs={'group_id': flow_group.id}) + f"?period={flow_group.period_start_date.strftime('%Y-%m-%d')}"
                
                Notification.objects.create(
                    family=family,
                    member=member,
                    notification_type='OVERBUDGET',
                    flow_group=flow_group,
                    message=message,
                    target_url=target_url
                )
                notifications_created += 1
    
    return notifications_created


def create_new_transaction_notification(transaction, exclude_member=None):
    """
    Cria notificações para uma transação nova ou editada.
    Remove notificações antigas da mesma transação antes de criar nova.
    
    Args:
        transaction: Transaction instance
        exclude_member: FamilyMember que não deve receber notificação (quem criou/editou)
    """
    from .models import FamilyMember, Notification, FlowGroupAccess
    
    print(f"[DEBUG NOTIF] Starting create_new_transaction_notification")
    print(f"[DEBUG NOTIF] Transaction: {transaction.id} - {transaction.description}")
    print(f"[DEBUG NOTIF] Exclude member: {exclude_member.user.username if exclude_member else 'None'}")
    
    family = transaction.flow_group.family
    flow_group = transaction.flow_group
    
    print(f"[DEBUG NOTIF] Family: {family.name}")
    print(f"[DEBUG NOTIF] FlowGroup: {flow_group.name}")
    print(f"[DEBUG NOTIF] FlowGroup type: {flow_group.group_type}")
    print(f"[DEBUG NOTIF] Is shared: {flow_group.is_shared}")
    print(f"[DEBUG NOTIF] Is kids group: {flow_group.is_kids_group}")
    
    # IMPORTANTE: Remove notificações antigas desta transação para evitar duplicatas
    deleted_count = Notification.objects.filter(
        transaction=transaction,
        notification_type='NEW_TRANSACTION',
        is_acknowledged=False
    ).delete()[0]
    print(f"[DEBUG NOTIF] Deleted {deleted_count} old notifications")
    
    # Determina quem deve receber a notificação
    members_to_notify = []
    
    # Para cada membro da família
    all_members = family.members.all()
    print(f"[DEBUG NOTIF] Total family members: {all_members.count()}")
    
    for member in all_members:
        print(f"[DEBUG NOTIF] Checking member: {member.user.username} (role: {member.role})")
        
        # Não notifica quem criou/editou a transação
        if exclude_member and member.id == exclude_member.id:
            print(f"[DEBUG NOTIF]   -> Skipped (is the editor)")
            continue
        
        # Verifica se o membro tem acesso ao FlowGroup
        has_access = False
        
        if member.role in ['ADMIN', 'PARENT']:
            print(f"[DEBUG NOTIF]   -> Member is ADMIN/PARENT")
            # Admin e Parent sempre veem shared groups
            if flow_group.is_shared:
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (shared group)")
            # Admin e Parent veem seus próprios groups
            elif flow_group.owner == member.user:
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (owner)")
            # Admin e Parent veem groups onde foram explicitamente adicionados
            elif flow_group.assigned_members.filter(id=member.id).exists():
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (assigned member)")
            # Admin e Parent sempre veem Kids groups
            elif flow_group.is_kids_group:
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (kids group)")
        
        elif member.role == 'CHILD':
            print(f"[DEBUG NOTIF]   -> Member is CHILD")
            # Children sempre veem Kids groups onde foram atribuídos
            if flow_group.is_kids_group and flow_group.assigned_children.filter(id=member.id).exists():
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (assigned to kids group)")
            # Children veem FlowGroups com acesso explícito
            elif FlowGroupAccess.objects.filter(member=member, flow_group=flow_group).exists():
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (explicit access)")
        
        # Lançamentos de crianças sempre notificam parents e admin
        if transaction.is_child_expense or transaction.is_child_manual_income:
            if member.role in ['ADMIN', 'PARENT']:
                has_access = True
                print(f"[DEBUG NOTIF]   -> Access granted (child transaction)")
        
        if has_access:
            members_to_notify.append(member)
            print(f"[DEBUG NOTIF]   -> WILL BE NOTIFIED")
        else:
            print(f"[DEBUG NOTIF]   -> NO ACCESS - will not be notified")
    
    print(f"[DEBUG NOTIF] Total members to notify: {len(members_to_notify)}")
    
    # Cria notificações
    notifications_created = 0
    for member in members_to_notify:
        creator_name = exclude_member.user.username if exclude_member else "Someone"
        
        # Determina a ação (added/updated)
        action = "added"  # Sempre "added" para simplificar
        
        message = f"{creator_name} {action} '{transaction.description}' in '{flow_group.name}'"
        
        # URL para o FlowGroup específico
        target_url = reverse('edit_flow_group', kwargs={'group_id': flow_group.id}) + f"?period={flow_group.period_start_date.strftime('%Y-%m-%d')}"
        
        print(f"[DEBUG NOTIF] Creating notification for {member.user.username}")
        print(f"[DEBUG NOTIF]   Message: {message}")
        print(f"[DEBUG NOTIF]   Target URL: {target_url}")
        
        notif = Notification.objects.create(
            family=family,
            member=member,
            notification_type='NEW_TRANSACTION',
            transaction=transaction,
            flow_group=flow_group,
            message=message,
            target_url=target_url
        )
        print(f"[DEBUG NOTIF]   Notification created with ID: {notif.id}")
        notifications_created += 1
    
    print(f"[DEBUG NOTIF] Total notifications created: {notifications_created}")
    return notifications_created


def get_accessible_flow_groups(family, member):
    """
    Retorna QuerySet de FlowGroups acessíveis ao membro.
    """
    from .models import FlowGroup, FlowGroupAccess
    from django.db.models import Q
    
    if member.role == 'ADMIN':
        # Admin vê tudo
        return FlowGroup.objects.filter(family=family)
    
    elif member.role == 'PARENT':
        # Parent vê: próprios, shared, kids groups, e onde foi explicitamente adicionado
        return FlowGroup.objects.filter(
            Q(family=family) & (
                Q(owner=member.user) |
                Q(is_shared=True) |
                Q(is_kids_group=True) |
                Q(assigned_members=member)
            )
        ).distinct()
    
    elif member.role == 'CHILD':
        # Child vê: kids groups onde foi atribuído e flow groups com acesso explícito
        accessible_ids = set()
        
        # Kids groups
        kids_groups = FlowGroup.objects.filter(
            family=family,
            is_kids_group=True,
            assigned_children=member
        ).values_list('id', flat=True)
        accessible_ids.update(kids_groups)
        
        # FlowGroups com acesso explícito
        explicit_access = FlowGroupAccess.objects.filter(
            member=member
        ).values_list('flow_group_id', flat=True)
        accessible_ids.update(explicit_access)
        
        return FlowGroup.objects.filter(id__in=accessible_ids)
    
    return FlowGroup.objects.none()


def check_and_create_notifications(family, member):
    """
    Verifica e cria todas as notificações necessárias para um membro.
    Chamada periodicamente ou quando o usuário acessa o sistema.
    """
    overdue_count = create_overdue_notifications(family, member)
    overbudget_count = create_overbudget_notifications(family, member)
    
    return {
        'overdue': overdue_count,
        'overbudget': overbudget_count
    }