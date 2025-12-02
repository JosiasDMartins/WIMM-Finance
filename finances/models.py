# finances/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone 
from decimal import Decimal 
from djmoney.models.fields import MoneyField
from moneyed import Money

# --- Flow Type Constants (used by views.py for filtering) ---

FLOW_TYPE_INCOME = 'INCOME'
EXPENSE_MAIN = 'EXPENSE_MAIN'
EXPENSE_SECONDARY = 'EXPENSE_SECONDARY'

# Define a constant that groups all expense types for easy filtering in views
FLOW_TYPE_EXPENSE = [EXPENSE_MAIN, EXPENSE_SECONDARY] 

# --- Custom User Model ---
class CustomUser(AbstractUser):
    language = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('pt-br', 'Português (Brasil)'),
        ],
        help_text=_("User's preferred language")
    )

# --- Core Finance Models ---

class SystemVersion(models.Model):
    """
    Stores the current system version in the database.
    Used to detect when updates are available.
    """
    version = models.CharField(
        max_length=50,
        help_text=_("Current system version (e.g., 1.0.0, 1.0.0-alpha1, 1.0.0-beta1, 2.0.0)")
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("System Version")
        verbose_name_plural = _("System Versions")

    def __str__(self):
        return f"v{self.version}"

    @classmethod
    def get_current_version(cls):
        """Returns the current version stored in DB, or None if not set."""
        version_obj = cls.objects.first()
        return version_obj.version if version_obj else None

    @classmethod
    def set_version(cls, version):
        """Sets or updates the system version in DB."""
        version_obj, created = cls.objects.get_or_create(id=1)
        version_obj.version = version
        version_obj.save()
        return version_obj


class SkippedUpdate(models.Model):
    """
    Tracks GitHub updates that the user chose to skip.
    When a user skips an update, it won't be shown again until a newer version is available.
    """
    version = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Version that was skipped (e.g., 1.0.0-alpha5)")
    )
    skipped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Skipped Update")
        verbose_name_plural = _("Skipped Updates")
        ordering = ['-skipped_at']

    def __str__(self):
        return f"Skipped v{self.version}"

    @classmethod
    def is_version_skipped(cls, version):
        """Check if a specific version was skipped."""
        return cls.objects.filter(version=version).exists()

    @classmethod
    def skip_version(cls, version):
        """Mark a version as skipped."""
        obj, created = cls.objects.get_or_create(version=version)
        return obj

    @classmethod
    def clear_skipped_versions(cls):
        """Clear all skipped versions (e.g., when user manually checks for updates)."""
        cls.objects.all().delete()


class Family(models.Model):
    """Represents a shared financial group (the 'umbrella account')."""
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class FamilyMember(models.Model):
    """Links a CustomUser to a Family and defines their role."""
    ROLES = [
        ('ADMIN', _('Admin')),
        ('PARENT', _('Parent')),
        ('CHILD', _('Child')),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='memberships')
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=10, choices=ROLES, default='PARENT')
    
    class Meta:
        unique_together = ('user', 'family')
        
    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()}) in {self.family.name}"

class FamilyConfiguration(models.Model):
    """Defines the financial cycle settings for the family."""
    PERIOD_TYPES = [
        ('M', _('Monthly')),
        ('B', _('Bi-weekly')),
        ('W', _('Weekly')),
    ]
    
    family = models.OneToOneField(Family, on_delete=models.CASCADE, related_name='configuration')
    # Day of the month for the start of the cycle (1-31)
    starting_day = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text=_("Day of the month (1-31) that defines the cycle start.")
    )
    period_type = models.CharField(max_length=1, choices=PERIOD_TYPES, default='M')
    # Base date used for calculating bi-weekly or weekly cycles
    base_date = models.DateField(default=timezone.localdate)

    # Moeda base da família (usada quando período não tem entrada em Period)
    base_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text=_("Base currency for the family (e.g., USD, BRL, EUR)")
    )

    # Bank reconciliation tolerance percentage
    bank_reconciliation_tolerance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(0.01), MaxValueValidator(100.00)],
        help_text=_("Percentage tolerance for bank reconciliation discrepancy warnings (e.g., 5.00 for 5%)")
    )

    def __str__(self):
        return f"Config for {self.family.name}"

class Period(models.Model):
    """
    Stores period information to maintain historical period boundaries and currency.
    Each period with transactions should have an entry here.
    """
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='periods')
    start_date = models.DateField(help_text=_("Start date of the period"))
    end_date = models.DateField(help_text=_("End date of the period"))
    period_type = models.CharField(max_length=1, choices=FamilyConfiguration.PERIOD_TYPES, help_text=_("Type of period"))
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text=_("Currency for this period")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        unique_together = ('family', 'start_date')
    
    def __str__(self):
        return f"{self.family.name} - {self.start_date} to {self.end_date} ({self.get_period_type_display()}) - {self.currency}"

class FlowGroup(models.Model):
    """
    Groups transactions (Income or Expense) and holds budget information.
    E.g., "Salary", "Groceries", "Rent".

    NEW: FlowGroups are now period-specific using period_start_date.
    Each period can have its own set of FlowGroups.
    """
    FLOW_TYPES = [
        (FLOW_TYPE_INCOME, _('Income')),
        (EXPENSE_MAIN, _('Main Expense (Essential)')),
        (EXPENSE_SECONDARY, _('Secondary Expense (Non-Essential)')),
    ]
    
    name = models.CharField(max_length=100)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='flow_groups')
    owner = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='owned_flow_groups')
    
    group_type = models.CharField(max_length=20, choices=FLOW_TYPES, default=EXPENSE_MAIN)
    
    # ATUALIZADO: MoneyField com moeda
    budgeted_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        default=Decimal('0.00')
    )
    
    # NEW: Period tracking - stores the start date of the period this group belongs to
    period_start_date = models.DateField(
        default=timezone.localdate,
        help_text=_("Start date of the period this FlowGroup belongs to")
    )

    # NEW: Sharing functionality
    is_shared = models.BooleanField(
        default=False,
        help_text=_("If True, this group is visible and editable by all Parents and Admins")
    )

    # NEW: Assigned members for Shared groups (Admins/Parents who can view/edit)
    assigned_members = models.ManyToManyField(
        FamilyMember,
        blank=True,
        related_name='shared_flow_groups',
        limit_choices_to={'role__in': ['ADMIN', 'PARENT']},
        help_text=_("Parents and Admins who have access to this Shared group")
    )

    # NEW: Kids group functionality
    is_kids_group = models.BooleanField(
        default=False,
        help_text=_("If True, this is a Kids group and budget becomes income for assigned children")
    )

    # NEW: Realized status for Kids groups (parents marking budget as given to child)
    realized = models.BooleanField(
        default=False,
        help_text=_("For Kids groups: marks if the budget has been given to the child (parents only)")
    )

    # NEW: Assigned children for Kids groups
    assigned_children = models.ManyToManyField(
        FamilyMember,
        blank=True,
        related_name='kids_flow_groups',
        limit_choices_to={'role': 'CHILD'},
        help_text=_("Children who have access to this Kids group")
    )

    # NEW: Investment flag - when checked, realized amounts go to investment balance
    is_investment = models.BooleanField(
        default=False,
        help_text=_("If True, realized amounts are added to investment balance and deducted from expense calculations")
    )

    # NEW: Recurring flag - when checked, FlowGroup is copied to new periods
    is_recurring = models.BooleanField(
        default=False,
        help_text=_("If True, this group and its fixed transactions will be copied to new periods")
    )

    # For reordering FlowGroups in a list/dashboard
    order = models.PositiveIntegerField(default=0, db_index=True) 

    class Meta:
        ordering = ['group_type', 'order', 'name']
        # FlowGroups are unique per family, name, and period
        unique_together = ('family', 'name', 'period_start_date')
        
    def __str__(self):
        return f"{self.name} ({self.family.name}) - {self.period_start_date}"
    
class Transaction(models.Model):
    """Individual financial entry."""
    description = models.CharField(max_length=255)

    # ATUALIZADO: MoneyField com moeda
    amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD'
    )

    date = models.DateField(default=timezone.localdate)

    # Realized status (consolidated/completed)
    realized = models.BooleanField(default=False, help_text=_("Whether this transaction has been consolidated/completed"))

    # NEW: Flag for manual income added by children (not from budget)
    is_child_manual_income = models.BooleanField(
        default=False,
        help_text=_("True if this is a manual income entry by a CHILD user (not from Kids group budget)")
    )

    is_child_expense = models.BooleanField(
        default=False,
        help_text=_("True if this is an expense added to a FlowGroup by a CHILD user)")
    )

    # NEW: Fixed/recurring flag - when checked, transaction is copied to new periods
    is_fixed = models.BooleanField(
        default=False,
        help_text=_("If True, this transaction will be auto-copied to new periods")
    )

    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, related_name='transactions')
    flow_group = models.ForeignKey(FlowGroup, on_delete=models.CASCADE, related_name='transactions')
    
    order = models.PositiveIntegerField(default=0, db_index=True) 
    
    class Meta:
        # Ordering by order ensures items within a group maintain user-defined order
        ordering = ['order', '-date'] 

    def __str__(self):
        return f"{self.description}: {self.amount}"

class FamilyMemberRoleHistory(models.Model):
    """
    Tracks role changes for family members across periods.
    Ensures dashboard displays correctly based on historical roles.
    """
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name='role_history')
    period_start_date = models.DateField(help_text=_("Start date of the period this role applies to"))
    role = models.CharField(max_length=10, choices=FamilyMember.ROLES)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_start_date']
        unique_together = ('member', 'period_start_date')
        indexes = [
            models.Index(fields=['member', 'period_start_date']),
        ]
    
    def __str__(self):
        return f"{self.member.user.username} - {self.get_role_display()} ({self.period_start_date})"

class FlowGroupAccess(models.Model):
    """Defines explicit detailed access to a FlowGroup for a specific member."""
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name='flow_access')
    flow_group = models.ForeignKey(FlowGroup, on_delete=models.CASCADE, related_name='shared_with')

    class Meta:
        unique_together = ('member', 'flow_group')

# --- Investment Model ---
class Investment(models.Model):
    """Simple model for tracking family investments."""
    name = models.CharField(max_length=150)
    
    # ATUALIZADO: MoneyField com moeda
    amount = MoneyField(
        max_digits=15,
        decimal_places=2,
        default_currency='USD',
        default=Decimal('0.00')
    )
    
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='investments')
    
    def __str__(self):
        return f"{self.name} ({self.amount})"

class BankBalance(models.Model):
    """
    Stores bank balance entries for reconciliation.
    Users input actual bank account values to compare with calculated balance.
    """
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='bank_balances')
    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_balances')
    description = models.CharField(max_length=255, help_text=_("Description of the bank account"))

    # MoneyField with currency
    amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        help_text=_("Current bank balance")
    )

    date = models.DateField(default=timezone.localdate, help_text=_("Date of balance check"))
    period_start_date = models.DateField(help_text=_("Period this balance belongs to"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', 'member']
    
    def __str__(self):
        member_name = self.member.user.username if self.member else "Family"
        return f"{self.description} - {member_name} - {self.amount} ({self.date})"


class Notification(models.Model):
    """
    Internal notification system.
    Notifies about overdue transactions, overbudget, and new releases.
    """
    NOTIFICATION_TYPES = [
        ('OVERDUE', _('Overdue Transaction')),
        ('OVERBUDGET', _('Over Budget')),
        ('NEW_TRANSACTION', _('New Transaction')),
    ]
    
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='notifications')
    member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    
    # Optional references to related objects
    transaction = models.ForeignKey(
        'Transaction', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    flow_group = models.ForeignKey(
        'FlowGroup', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    # Notification message
    message = models.TextField()
    
    # URL notification rection
    target_url = models.CharField(max_length=500, blank=True)
    
    # Status control
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['member', 'is_acknowledged', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.member.user.username} - {'Ack' if self.is_acknowledged else 'New'}"
    
    def acknowledge(self):
        """Marca a notificação como reconhecida."""
        self.is_acknowledged = True
        self.acknowledged_at = timezone.now()
        self.save()


class PasswordResetCode(models.Model):
    """
    Stores password reset verification codes.
    Each code is valid for a limited time and can only be used once.
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='password_reset_codes'
    )
    code = models.CharField(
        max_length=10,
        help_text=_("5-digit verification code sent to user's email")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'code', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Reset code for {self.user.username} - {'Used' if self.is_used else 'Active'}"

    def is_valid(self):
        """Check if the code is still valid (not expired and not used)."""
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self, ip_address=None):
        """Mark the code as used."""
        self.is_used = True
        self.used_at = timezone.now()
        if ip_address:
            self.ip_address = ip_address
        self.save()

    @classmethod
    def cleanup_expired(cls):
        """Remove expired codes older than 24 hours."""
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        cls.objects.filter(expires_at__lt=cutoff).delete()