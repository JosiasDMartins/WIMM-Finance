from django import forms
from django.forms import modelformset_factory
from django.contrib.auth import get_user_model # <-- Import necessário!

from .models import FamilyConfiguration, FamilyMember, FlowGroup, Transaction, Investment, CustomUser



# --- Configuration Form ---
class FamilyConfigurationForm(forms.ModelForm):
    class Meta:
        model = FamilyConfiguration
        fields = ['closing_day', 'period_type', 'base_date']
        widgets = {
            'closing_day': forms.NumberInput(attrs={'class': 'form-input'}),
            'period_type': forms.RadioSelect(choices=FamilyConfiguration.PERIOD_TYPES),
            'base_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

# --- FlowGroup Form ---
class FlowGroupForm(forms.ModelForm):
    class Meta:
        model = FlowGroup
        fields = ['name', 'budgeted_amount', 'group_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'budgeted_amount': forms.NumberInput(attrs={'class': 'form-input'}),
            'group_type': forms.Select(attrs={'class': 'form-select'}),
        }

# --- Transaction Form (for spreadsheet-like editing) ---
# We use a simple ModelForm, but the real magic will be in the ModelFormSet 
# used in the view for FlowGroup.html

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

# --- Investment Form ---
class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Investment
        fields = ['name', 'amount']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input'}),
        }

class AddMemberForm(forms.Form):
    """
    Formulário para o administrador criar um novo usuário e membro familiar, 
    permitindo username, password e um email opcional.
    """
    ROLES = FamilyMember.ROLES

    # Campos de formulário (os mesmos)
    username = forms.CharField(
        label='Username (User ID)',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'placeholder': 'e.g., john.doe', 'required': True})
    )
    email = forms.EmailField(
        label='E-mail (Opcional)',
        max_length=254,
        required=False,
        widget=forms.EmailInput(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'placeholder': 'e.g., example@email.com'})
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'required': True})
    )
    role = forms.ChoiceField(
        label='Função',
        choices=ROLES,
        initial='PARENT',
        widget=forms.Select(attrs={'class': 'w-full border rounded-lg bg-background-light dark:bg-background-dark border-slate-300 dark:border-slate-700 focus:ring-primary focus:border-primary text-slate-800 dark:text-slate-200 p-2', 'required': True})
    )
    
    def clean_username(self):
        username = self.cleaned_data['username']
        # CORREÇÃO: Chama get_user_model() diretamente dentro do método
        UserModel = get_user_model() 
        if UserModel.objects.filter(username__iexact=username).exists(): 
             raise forms.ValidationError("Este nome de usuário já está sendo usado por outra conta.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # CORREÇÃO: Chama get_user_model() diretamente dentro do método
            UserModel = get_user_model() 
            if UserModel.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError("Este e-mail já está em uso por outra conta.")
        return email