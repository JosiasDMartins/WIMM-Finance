from django import forms
from django.forms import modelformset_factory
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
    # Obtém as opções de ROLE do modelo FamilyMember
    ROLES = FamilyMember.ROLES

    email = forms.EmailField(
        label='Endereço de E-mail do Novo Membro',
        max_length=254,
        # Adicione widgets para estilização se necessário (ex: widgets.EmailInput)
    )
    role = forms.ChoiceField(
        label='Função',
        choices=ROLES,
        initial='PARENT'
    )
    
    # Opcional: Adiciona a família para validações futuras
    def __init__(self, *args, **kwargs):
        self.family = kwargs.pop('family', None)
        super().__init__(*args, **kwargs)
        
    # Exemplo de validação customizada:
    def clean_email(self):
        email = self.cleaned_data['email']
        # Verifica se o usuário já é membro da família
        try:
            user = CustomUser.objects.get(email__iexact=email)
            if FamilyMember.objects.filter(user=user, family=self.family).exists():
                 raise forms.ValidationError("Este usuário já é membro da sua família.")
        except CustomUser.DoesNotExist:
            # Não existe usuário, pode passar para a próxima etapa (a view tenta criar/enviar convite)
            pass
        
        return email        