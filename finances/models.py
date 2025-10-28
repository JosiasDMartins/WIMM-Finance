# models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils import timezone # FIX: This line was missing!

# --- Custom User Model ---
class CustomUser(AbstractUser):
    # Add any extra fields here in the future
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
        ('PARENT', 'Parent'), # Changed from MEMBER to PARENT for clarity based on 'child' logic
        ('CHILD', 'Child'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='memberships')
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=10, choices=ROLES, default='PARENT')
    
    class Meta:
        unique_together = ('user', 'family')
        verbose_name_plural = "Family Members"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()}) in {self.family.name}"

class FamilyConfiguration(models.Model):
    """Stores period and cycle settings for the Family."""
    PERIOD_TYPES = [
        ('M', 'Monthly'),
        ('B', 'Bi-weekly'),
    ]
    family = models.OneToOneField(Family, on_delete=models.CASCADE, related_name='configuration')
    closing_day = models.IntegerField(
        default=30,
        help_text=_("Day of the month (1-31) that defines the cycle closure for 'Monthly' period.")
    )
    period_type = models.CharField(max_length=1, choices=PERIOD_TYPES, default='M')
    base_date = models.DateField(
        null=True, blank=True,
        help_text=_("Start date used as a reference point, especially for 'Bi-weekly' cycles.")
    )

    def __str__(self):
        return f"Config for {self.family.name}"

class FlowGroup(models.Model):
    """The 'partial table' for budgeting and grouping transactions."""
    GROUP_TYPES = [
        ('EXPENSE_SECONDARY', 'Secondary Expense Flow'),
        ('EXPENSE_MAIN', 'Main Expense Flow'),
        ('INCOME', 'Income Flow'),
    ]
    name = models.CharField(max_length=150)
    budgeted_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='flow_groups')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='owned_flow_groups')
    group_type = models.CharField(max_length=20, choices=GROUP_TYPES, default='EXPENSE_SECONDARY')
    
    # NEW FIELD: Handles the 'Compartilhado' logic
    is_shared = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.name} ({self.family.name})"
    
class Transaction(models.Model):
    """Individual financial entry."""
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    
    # Updated to link to FamilyMember, fulfilling your requirement
    member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, related_name='transactions')
    flow_group = models.ForeignKey(FlowGroup, on_delete=models.CASCADE, related_name='transactions')
    
    # Added for reordering logic
    order = models.PositiveIntegerField(default=0, db_index=True) 
    
    class Meta:
        ordering = ['order']

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
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='investments')
    
    def __str__(self):
        return self.name