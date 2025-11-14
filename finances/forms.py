# finances/forms.py

from django import forms
from django.contrib.auth import get_user_model
from .models import (
    Family, FamilyMember, FamilyConfiguration, FlowGroup, 
    Transaction, Investment, EXPENSE_MAIN
)
from django.forms import modelformset_factory
from djmoney.forms.fields import MoneyField as MoneyFormField


# Lista completa de moedas G20 e BRICS
CURRENCY_CHOICES = [
    ('BRL', 'BRL - Brazilian Real (R$)'),
    ('USD', 'USD - US Dollar ($)'),
    ('EUR', 'EUR - Euro (â‚¬)'),
    ('GBP', 'GBP - British Pound (Â£)'),
    ('JPY', 'JPY - Japanese Yen (Â¥)'),
    ('CNY', 'CNY - Chinese Yuan (Â¥)'),
    ('INR', 'INR - Indian Rupee (â‚¹)'),
    ('RUB', 'RUB - Russian Ruble (â‚½)'),
    ('ZAR', 'ZAR - South African Rand (R)'),
    ('CAD', 'CAD - Canadian Dollar ($)'),
    ('AUD', 'AUD - Australian Dollar ($)'),
    ('MXN', 'MXN - Mexican Peso ($)'),
    ('KRW', 'KRW - South Korean Won (â‚©)'),
    ('TRY', 'TRY - Turkish Lira (â‚º)'),
    ('IDR', 'IDR - Indonesian Rupiah (Rp)'),
    ('SAR', 'SAR - Saudi Riyal (ï·¼)'),
    ('ARS', 'ARS - Argentine Peso ($)'),
    ('EGP', 'EGP - Egyptian Pound (Â£)'),
    ('AED', 'AED - UAE Dirham (Ø¯.Ø¥)'),
    ('ETB', 'ETB - Ethiopian Birr (Br)'),
]


# --- Initial Setup Form (First Time User) ---
class InitialSetupForm(forms.Form):
    """
    Form for creating the first admin user, family, and configuration
    during initial setup.
    """
    # User fields
    username = forms.CharField(
        max_length=150,
        label='Admin Username',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'Choose a username'
        })
    )
    
    email = forms.EmailField(
        required=False,
        label='Email (Optional)',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'your@email.com'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'Create a password'
        }),
        label='Password',
        min_length=6
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'Confirm your password'
        }),
        label='Confirm Password'
    )
    
    # Family fields
    family_name = forms.CharField(
        max_length=100,
        label='Family Name',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'e.g., Smith Family'
        })
    )
    
    # Configuration fields
    period_type = forms.ChoiceField(
        choices=FamilyConfiguration.PERIOD_TYPES,
        initial='M',
        label='Period Type',
        widget=forms.RadioSelect(attrs={'class': 'form-radio'})
    )
    
    starting_day = forms.IntegerField(
        initial=1,
        min_value=1,
        max_value=31,
        label='Starting Day of Month',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': '1-31'
        })
    )
    
    base_date = forms.DateField(
        required=False,
        label='Base Date for Bi-weekly/Weekly Cycles',
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'type': 'date'
        })
    )
    
    # SeleÃ§Ã£o de moeda base
    base_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial='BRL',
        label='Base Currency',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent'
        })
    )
    
    def clean_username(self):
        username = self.cleaned_data['username']
        UserModel = get_user_model()
        if UserModel.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            UserModel = get_user_model()
            if UserModel.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError("An account with this email already exists.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")
        
        return cleaned_data

    
# --- Configuration Form ---
class FamilyConfigurationForm(forms.ModelForm):
    base_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label='Base Currency',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent'
        })
    )
    
    class Meta:
        model = FamilyConfiguration
        fields = ['starting_day', 'period_type', 'base_date', 'base_currency']
        widgets = {
            'starting_day': forms.NumberInput(attrs={'class': 'form-input'}),
            'period_type': forms.RadioSelect(choices=FamilyConfiguration.PERIOD_TYPES),
            'base_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

# --- FlowGroup Form ---
class FlowGroupForm(forms.ModelForm):
    # Override budgeted_amount to use only number input (no currency selector)
    budgeted_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        }),
        label='Budgeted Amount'
    )
    
    # Add field for selecting ONLY PARENTS for Shared groups (exclude ADMIN)
    assigned_members = forms.ModelMultipleChoiceField(
        queryset=FamilyMember.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'members-checkbox'}),
        label='Assign Members (Parents)'
    )
    
    # Add field for selecting children (will be populated dynamically)
    assigned_children = forms.ModelMultipleChoiceField(
        queryset=FamilyMember.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'kids-checkbox'}),
        label='Assign Children'
    )
    
    class Meta:
        model = FlowGroup
        fields = ['name', 'budgeted_amount', 'is_shared', 'is_kids_group', 'is_investment', 'assigned_members', 'assigned_children']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'is_shared': forms.CheckboxInput(attrs={'class': 'shared-checkbox'}),
            'is_kids_group': forms.CheckboxInput(attrs={'class': 'kids-checkbox'}),
            'is_investment': forms.CheckboxInput(attrs={'class': 'investment-checkbox'}),
        }
    
    def __init__(self, *args, **kwargs):
        family = kwargs.pop('family', None)
        super().__init__(*args, **kwargs)
        
        # If editing existing FlowGroup, populate with current amount value (extract from Money)
        # CRITICAL: This must happen AFTER super().__init__ to override Django's automatic population
        if self.instance and self.instance.pk:
            budgeted = self.instance.budgeted_amount
            if budgeted is not None:
                if hasattr(budgeted, 'amount'):
                    # Extract numeric value from Money object
                    amount_value = budgeted.amount
                else:
                    amount_value = budgeted
                
                # Force the value into the field's widget
                self.fields['budgeted_amount'].initial = amount_value
                # Also set it in the form's data if it's bound
                if self.data.get('budgeted_amount') is None and not self.is_bound:
                    self.initial['budgeted_amount'] = amount_value
        
        # Populate members (ONLY PARENTS, exclude ADMIN) queryset if family is provided
        # Admins don't need to be in assigned_members since they have access to everything
        if family:
            self.fields['assigned_members'].queryset = FamilyMember.objects.filter(
                family=family,
                role='PARENT'  # Only PARENT, not ADMIN
            ).select_related('user').order_by('user__username')
            
            # Populate children queryset if family is provided
            self.fields['assigned_children'].queryset = FamilyMember.objects.filter(
                family=family,
                role='CHILD'
            ).select_related('user').order_by('user__username')

# --- Transaction Form (for spreadsheet-like editing) ---
class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['description', 'amount', 'date']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'editable-cell', 'placeholder': 'Description'}),
            # amount Ã© MoneyField - widget automÃ¡tico
            'amount': forms.NumberInput(attrs={'class': 'editable-cell', 'placeholder': 'Amount'}),
            'date': forms.DateInput(attrs={'class': 'editable-cell', 'type': 'date'}),
        }

TransactionFormSet = modelformset_factory(
    Transaction, 
    form=TransactionForm, 
    extra=1, # Always show one empty row for adding new
    can_delete=True
)

# --- Investment Form ---
class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Investment
        fields = ['name', 'amount']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Stocks, Savings Account'}),
            # amount Ã© MoneyField - widget automÃ¡tico
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00'}),
        }


# --- Member Management Form ---
class FamilyMemberForm(forms.ModelForm):
    # This form is for updating an existing member's role
    class Meta:
        model = FamilyMember
        fields = ['role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

# Simplified form to link an existing user by email
class AddMemberForm(forms.Form):
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )
    role = forms.ChoiceField(
        choices=FamilyMember.ROLES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

# Form to create a new User and FamilyMember in one go
class NewUserAndMemberForm(forms.Form):
    """
    Form for an administrator to create a new user and family member, 
    allowing username, password, and an optional email.
    """
    ROLES = FamilyMember.ROLES
    
    username = forms.CharField(
        label='Username (User ID)',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'required': True})
    )
    email = forms.EmailField(
        label='Email (Optional)',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'required': True})
    )
    role = forms.ChoiceField(
        label='Role',
        choices=ROLES,
        initial='PARENT',
        widget=forms.Select(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'required': True})
    )
    
    def clean_username(self):
        username = self.cleaned_data['username']
        # Get the User model dynamically
        UserModel = get_user_model() 
        if UserModel.objects.filter(username__iexact=username).exists(): 
             raise forms.ValidationError("This username is already in use by another account.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Get the User model dynamically
            UserModel = get_user_model() 
            if UserModel.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError("An account with this email address already exists.")
        return email
