# finances/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils import timezone 
from decimal import Decimal 

# --- Flow Type Constants (used by views.py for filtering) ---

FLOW_TYPE_INCOME = 'INCOME'
EXPENSE_MAIN = 'EXPENSE_MAIN'
EXPENSE_SECONDARY = 'EXPENSE_SECONDARY'

# Define a constant that groups all expense types for easy filtering in views
FLOW_TYPE_EXPENSE = [EXPENSE_MAIN, EXPENSE_SECONDARY] 

# --- Custom User Model ---
class CustomUser(AbstractUser):
    pass

# --- Core Finance Models ---

class Family(models.Model):
    """Represents a shared financial group (the 'umbrella account')."""
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class FamilyMember(models.Model):
    """Links a CustomUser to a Family and defines their role."""
    ROLES = [
        ('ADMIN', 'Admin'),
        ('PARENT', 'Parent'),
        ('CHILD', 'Child'),
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
        ('M', 'Monthly'),
        ('B', 'Bi-weekly'),
        ('W', 'Weekly'),
    ]
    
    family = models.OneToOneField(Family, on_delete=models.CASCADE, related_name='configuration')
    # Day of the month for the closing of the cycle (1-31)
    closing_day = models.PositiveSmallIntegerField(
        default=5, 
        validators=[MinValueValidator(1)],
        help_text="Day of the month (1-31) that defines the cycle closure."
    )
    period_type = models.CharField(max_length=1, choices=PERIOD_TYPES, default='M')
    # Base date used for calculating bi-weekly or weekly cycles
    base_date = models.DateField(default=timezone.localdate) 

    def __str__(self):
        return f"Config for {self.family.name}"

class FlowGroup(models.Model):
    """
    Groups transactions (Income or Expense) and holds budget information.
    E.g., "Salary", "Groceries", "Rent".
    """
    FLOW_TYPES = [
        (FLOW_TYPE_INCOME, 'Income'),
        (EXPENSE_MAIN, 'Main Expense (Essential)'),
        (EXPENSE_SECONDARY, 'Secondary Expense (Non-Essential)'),
    ]
    
    name = models.CharField(max_length=100)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='flow_groups')
    owner = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='owned_flow_groups')
    
    group_type = models.CharField(max_length=20, choices=FLOW_TYPES, default=EXPENSE_MAIN)
    budgeted_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # For reordering FlowGroups in a list/dashboard
    order = models.PositiveIntegerField(default=0, db_index=True) 

    class Meta:
        ordering = ['group_type', 'order', 'name']
        unique_together = ('family', 'name')
        
    def __str__(self):
        return f"{self.name} ({self.family.name})"
    
class Transaction(models.Model):
    """Individual financial entry."""
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    
    # New field: realized status (consolidated/completed)
    realized = models.BooleanField(default=False, help_text="Whether this transaction has been consolidated/completed")
    
    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, related_name='transactions')
    flow_group = models.ForeignKey(FlowGroup, on_delete=models.CASCADE, related_name='transactions')
    
    order = models.PositiveIntegerField(default=0, db_index=True) 
    
    class Meta:
        # Ordering by order ensures items within a group maintain user-defined order
        ordering = ['order', '-date'] 

    def __str__(self):
        return f"{self.description}: {self.amount}"

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
    # The current value of the investment
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00')) 
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='investments')
    
    def __str__(self):
        return f"{self.name} ({self.amount})"
