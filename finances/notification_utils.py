# finances/notification_utils.py

from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext as _
from decimal import Decimal


def create_overdue_notifications(family, member):
    """
    Creates notifications for overdue transactions (realized=False and past date).
    Does not create duplicates for transactions that have already been notified.
    """
    from .models import Transaction, Notification, FlowGroup
    
    today = timezone.localdate()
    
    # Search for incomplete and overdue transactions
    overdue_transactions = Transaction.objects.filter(
        flow_group__family=family,
        realized=False,
        date__lt=today
    ).select_related('flow_group', 'member')
    
    # Filter by member permissions
    accessible_flow_groups = get_accessible_flow_groups(family, member)
    overdue_transactions = overdue_transactions.filter(flow_group__in=accessible_flow_groups)
    
    notifications_created = 0
    
    for transaction in overdue_transactions:
        # Checks if a notification already exists for this transaction (acknowledged or not).
        # Once user dismisses an overdue notification, we don't create it again.
        existing = Notification.objects.filter(
            member=member,
            transaction=transaction,
            notification_type='OVERDUE'
        ).exists()

        if not existing:
            days_overdue = (today - transaction.date).days
            if days_overdue == 1:
                message = _("Transaction '%(description)s' is %(days)d day overdue") % {
                    'description': transaction.description,
                    'days': days_overdue
                }
            else:
                message = _("Transaction '%(description)s' is %(days)d days overdue") % {
                    'description': transaction.description,
                    'days': days_overdue
                }

            # URL for the FlowGroup
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
    
    # Search FlowGroups accessible to the member
    accessible_flow_groups = get_accessible_flow_groups(family, member)
    
    # Filter only Expense Flow Groups (EXPENSE MAIN and EXPENSE SECONDARY)
    expense_groups = accessible_flow_groups.filter(
        Q(group_type='EXPENSE_MAIN') | Q(group_type='EXPENSE_SECONDARY')
    )
    
    notifications_created = 0
    
    for flow_group in expense_groups:
        # Calculate total amount spent
        realized_total = flow_group.transactions.filter(realized=True).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        budgeted = flow_group.budgeted_amount.amount if hasattr(flow_group.budgeted_amount, 'amount') else flow_group.budgeted_amount
        
        # Verifica se está acima do orçamento
        if realized_total > budgeted:
            # Check if a notification already exists (acknowledged or not).
            # Once user dismisses an overbudget notification, we don't create it again.
            existing = Notification.objects.filter(
                member=member,
                flow_group=flow_group,
                notification_type='OVERBUDGET'
            ).exists()

            if not existing:
                over_amount = (realized_total - budgeted).quantize(Decimal('0.01'))
                message = _("'%(name)s' is over budget by %(amount)s") % {
                    'name': flow_group.name,
                    'amount': over_amount
                }

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
    Creates notifications for a new or edited transaction.
    Removes old notifications from the same transaction before creating a new one.

    Args:
    transaction: Transaction instance
    exclude_member: FamilyMember who should not receive notifications (who created/edited)
    """
    from .models import FamilyMember, Notification

    debug_enabled = getattr(settings, 'DEBUG', False)

    if debug_enabled:
        print(f"[DEBUG NOTIF] Starting create_new_transaction_notification")
        print(f"[DEBUG NOTIF] Transaction: {transaction.id} - {transaction.description}")
        print(f"[DEBUG NOTIF] Exclude member: {exclude_member.user.username if exclude_member else 'None'}")

    family = transaction.flow_group.family
    flow_group = transaction.flow_group

    if debug_enabled:
        print(f"[DEBUG NOTIF] Family: {family.name}")
        print(f"[DEBUG NOTIF] FlowGroup: {flow_group.name} (ID: {flow_group.id})")
        print(f"[DEBUG NOTIF] FlowGroup type: {flow_group.group_type}")
        print(f"[DEBUG NOTIF] Is shared: {flow_group.is_shared}")
        print(f"[DEBUG NOTIF] Is kids group: {flow_group.is_kids_group}")
        print(f"[DEBUG NOTIF] Transaction is_child_expense: {transaction.is_child_expense}")
        print(f"[DEBUG NOTIF] Transaction is_child_manual_income: {transaction.is_child_manual_income}")

    # IMPORTANT: Remove old notifications for this transaction to avoid duplicates.
    deleted_count = Notification.objects.filter(
        transaction=transaction,
        notification_type='NEW_TRANSACTION',
        is_acknowledged=False
    ).delete()[0]

    if debug_enabled:
        print(f"[DEBUG NOTIF] Deleted {deleted_count} old notifications")
    
    # Determines who should receive the notification
    members_to_notify = []

    # For each family member
    all_members = family.members.all()

    if debug_enabled:
        print(f"[DEBUG NOTIF] Total family members: {all_members.count()}")

    for member in all_members:
        if debug_enabled:
            print(f"[DEBUG NOTIF] Checking member: {member.user.username} (role: {member.role}, ID: {member.id})")

        # Does not notify who created/edited the transaction
        #if exclude_member and member.id == exclude_member.id:
        #    if debug_enabled:
        #        print(f"[DEBUG NOTIF]   -> Skipped (is the editor)")
        #    continue

        # Verifica se o membro tem acesso ao FlowGroup
        has_access = check_member_access_to_flow_group(member, flow_group, transaction)

        if has_access:
            members_to_notify.append(member)
            if debug_enabled:
                print(f"[DEBUG NOTIF]   -> WILL BE NOTIFIED")
        else:
            if debug_enabled:
                print(f"[DEBUG NOTIF]   -> NO ACCESS - will not be notified")

    if debug_enabled:
        print(f"[DEBUG NOTIF] Total members to notify: {len(members_to_notify)}")
    
    # Cria notificações
    notifications_created = 0
    for member in members_to_notify:
        creator_name = exclude_member.user.username if exclude_member else _("Someone")

        # Mensagem simplificada
        message = _("%(creator)s added '%(description)s' in '%(group)s'") % {
            'creator': creator_name,
            'description': transaction.description,
            'group': flow_group.name
        }

        # URL para o FlowGroup específico
        target_url = reverse('edit_flow_group', kwargs={'group_id': flow_group.id}) + f"?period={flow_group.period_start_date.strftime('%Y-%m-%d')}"

        if debug_enabled:
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

        if debug_enabled:
            print(f"[DEBUG NOTIF]   Notification created with ID: {notif.id}")

        notifications_created += 1

    if debug_enabled:
        print(f"[DEBUG NOTIF] Total notifications created: {notifications_created}")

    return notifications_created


def check_member_access_to_flow_group(member, flow_group, transaction=None):
    """
    Checks if a member has access to a FlowGroup.
    Considers child transactions.

    Args:

    member: FamilyMember instance
    flow_group: FlowGroup instance
    transaction: Transaction instance (optional, for special cases)

    Returns:
    bool: True if the member has access

    """
    from .models import FlowGroupAccess

    debug_enabled = getattr(settings, 'DEBUG', False)

    if debug_enabled:
        print(f"[DEBUG ACCESS] Checking access for {member.user.username} to {flow_group.name}")
        print(f"[DEBUG ACCESS]   Member role: {member.role}")
        print(f"[DEBUG ACCESS]   FlowGroup owner: {flow_group.owner.username if flow_group.owner else 'None'}")
        print(f"[DEBUG ACCESS]   Is shared: {flow_group.is_shared}")
        print(f"[DEBUG ACCESS]   Is kids group: {flow_group.is_kids_group}")

    # ADMIN sempre tem acesso
    if member.role == 'ADMIN':
        if debug_enabled:
            print(f"[DEBUG ACCESS]   -> Access GRANTED (ADMIN)")
        return True
    
    # PARENT verifica vários critérios
    if member.role == 'PARENT':
        # Dono do FlowGroup
        if flow_group.owner == member.user:
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (owner)")
            return True

        # FlowGroup compartilhado
        if flow_group.is_shared:
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (shared group)")
            return True

        # Kids group (PARENT sempre vê)
        if flow_group.is_kids_group:
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (kids group)")
            return True

        # Membro explicitamente atribuído
        if flow_group.assigned_members.filter(id=member.id).exists():
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (assigned member)")
            return True

        # Transação de criança (PARENT sempre vê)
        if transaction and (transaction.is_child_expense or transaction.is_child_manual_income):
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (child transaction)")
            return True
    
    # CHILD verifica critérios específicos
    if member.role == 'CHILD':
        # Kids group onde foi atribuído
        if flow_group.is_kids_group and flow_group.assigned_children.filter(id=member.id).exists():
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (assigned to kids group)")
            return True

        # Acesso explícito via FlowGroupAccess
        if FlowGroupAccess.objects.filter(member=member, flow_group=flow_group).exists():
            if debug_enabled:
                print(f"[DEBUG ACCESS]   -> Access GRANTED (explicit access)")
            return True

    if debug_enabled:
        print(f"[DEBUG ACCESS]   -> Access DENIED")
    return False


def get_accessible_flow_groups(family, member):
    """
    Returns a QuerySet of FlowGroups accessible to the member.
    """
    from .models import FlowGroup, FlowGroupAccess
    from django.db.models import Q
    
    if member.role == 'ADMIN':
        # Admin vê tudo
        return FlowGroup.objects.filter(family=family)
    
    elif member.role == 'PARENT':
        # Parent views: own, shared, kids groups, and where it was explicitly added
        return FlowGroup.objects.filter(
            Q(family=family) & (
                Q(owner=member.user) |
                Q(is_shared=True) |
                Q(is_kids_group=True) |
                Q(assigned_members=member)
            )
        ).distinct()
    
    elif member.role == 'CHILD':
        # Child sees: kids groups where it was assigned and flow groups with explicit access
        accessible_ids = set()
        
        # Kids groups
        kids_groups = FlowGroup.objects.filter(
            family=family,
            is_kids_group=True,
            assigned_children=member
        ).values_list('id', flat=True)
        accessible_ids.update(kids_groups)
        
        # FlowGroups with explicit access
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