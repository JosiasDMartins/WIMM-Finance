# finances/forms.py

from django import forms
from django.forms import modelformset_factory
from django.contrib.auth import get_user_model

from .models import FamilyConfiguration, FamilyMember, FlowGroup, Transaction, Investment, CustomUser

class InitialSetupForm(forms.Form):
    """
    Form for initial setup of the WIMM application.
    Creates the first admin user, family, and configuration.
    """
    
    # Family Information
    family_name = forms.CharField(
        max_length=100,
        label='Family Name',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'e.g., The Smiths, Johnson Family'
        }),
        help_text='The name of your family financial group'
    )
    
    # Administrator Account
    username = forms.CharField(
        max_length=150,
        label='Username',
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
            'placeholder': 'your.email@example.com'
        })
    )
    
    password = forms.CharField(
        min_length=6,
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'Minimum 6 characters'
        }),
        help_text='Must be at least 6 characters long'
    )
    
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'placeholder': 'Re-enter your password'
        })
    )
    
    # Financial Configuration
    period_type = forms.ChoiceField(
        choices=FamilyConfiguration.PERIOD_TYPES,
        initial='M',
        label='Period Frequency',
        widget=forms.RadioSelect(attrs={
            'class': 'form-radio text-teal-600 focus:ring-teal-500'
        })
    )
    
    starting_day = forms.IntegerField(
        min_value=1,
        max_value=31,
        initial=1,
        label='Starting Day (for Monthly Cycle)',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent',
            'min': '1',
            'max': '31'
        }),
        help_text='Day of the month (1-31) when your budget cycle starts'
    )
    
    base_date = forms.DateField(
        required=False,
        label='Base Date (for Bi-weekly/Weekly cycles)',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent'
        }),
        help_text='Reference date for calculating bi-weekly/weekly periods'
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
    class Meta:
        model = FamilyConfiguration
        fields = ['starting_day', 'period_type', 'base_date']
        widgets = {
            'starting_day': forms.NumberInput(attrs={'class': 'form-input'}),
            'period_type': forms.RadioSelect(choices=FamilyConfiguration.PERIOD_TYPES),
            'base_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

# --- FlowGroup Form ---
class FlowGroupForm(forms.ModelForm):
    # Add field for selecting Parents/Admins for Shared groups
    assigned_members = forms.ModelMultipleChoiceField(
        queryset=FamilyMember.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'members-checkbox'}),
        label='Assign Members (Parents/Admins)'
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
            'budgeted_amount': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_shared': forms.CheckboxInput(attrs={'class': 'shared-checkbox'}),
            'is_kids_group': forms.CheckboxInput(attrs={'class': 'kids-checkbox'}),
            'is_investment': forms.CheckboxInput(attrs={'class': 'investment-checkbox'}),
        }
    
    def __init__(self, *args, **kwargs):
        family = kwargs.pop('family', None)
        super().__init__(*args, **kwargs)
        
        # Populate members (Parents/Admins) queryset if family is provided
        if family:
            self.fields['assigned_members'].queryset = FamilyMember.objects.filter(
                family=family,
                role__in=['ADMIN', 'PARENT']
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
