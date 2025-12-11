import io
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model, logout as auth_logout, login
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db import transaction as db_transaction
from django.db.utils import OperationalError
from django.core.management import call_command
from django.contrib.auth import update_session_auth_hash

# Importações relativas do app (.. sobe um nível, de /views/ para /finances/)
from ..models import Family, FamilyMember, FamilyConfiguration, SystemVersion
from ..forms import InitialSetupForm
from ..utils import get_current_period_dates

# Importações de utils locais (mesmo pacote /views/)
from .views_utils import (
    get_family_context,
    get_base_template_context,
)

from ..context_processors import VERSION


def initial_setup_view(request):
    """Initial setup view for the first installation."""
    
    # === PASSO 1: Garantir que o banco de dados e as tabelas existam ===
    try:
        UserModel = get_user_model()
        users_exist = UserModel.objects.exists()
        
        if users_exist:
            if request.user.is_authenticated:
                return redirect('dashboard')
            return redirect('auth_login')
            
    except OperationalError as e:
        if request.method != 'POST':
            context = {
                'needs_migration': True,
                'error_message': _('Database setup required. Running migrations...')
            }
            try:
                out = io.StringIO()
                call_command('migrate', '--noinput', stdout=out, stderr=out)
                migration_output = out.getvalue()
                context['migration_success'] = True
                context['migration_output'] = migration_output
            except Exception as migration_error:
                context['migration_error'] = str(migration_error)
            
            return render(request, 'finances/setup.html', {'form': InitialSetupForm(), **context})
    
    except Exception as e:
        messages.error(request, _("Database error: %(error)s") % {'error': str(e)})
        context = {
            'form': InitialSetupForm(),
            'database_error': str(e)
        }
        return render(request, 'finances/setup.html', context)
    
    # === PASSO 2: Lidar com o envio do formulário ===
    if request.method == 'POST':
        form = InitialSetupForm(request.POST)
        
        if form.is_valid():
            try:
                with db_transaction.atomic():
                    UserModel = get_user_model()
                    admin_user = UserModel.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data.get('email', ''),
                        password=form.cleaned_data['password']
                    )
                    
                    family = Family.objects.create(
                        name=form.cleaned_data['family_name']
                    )
                    
                    FamilyMember.objects.create(
                        user=admin_user,
                        family=family,
                        role='ADMIN'
                    )
                    
                    base_date = form.cleaned_data.get('base_date') or timezone.localdate()
                    base_currency = form.cleaned_data.get('base_currency', 'BRL')
                    
                    FamilyConfiguration.objects.create(
                        family=family,
                        starting_day=form.cleaned_data['starting_day'],
                        period_type=form.cleaned_data['period_type'],
                        base_date=base_date,
                        base_currency=base_currency
                    )
                    
                    SystemVersion.set_version(VERSION)
                    
                    login(request, admin_user)
                    
                    messages.success(
                        request,
                        _("Welcome to SweetMoney! Your family '%(family_name)s' has been created successfully.") % {'family_name': family.name}
                    )
                    return redirect('dashboard')

            except Exception as e:
                messages.error(
                    request,
                    _("An error occurred during setup: %(error)s. Please try again.") % {'error': str(e)}
                )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        initial_data = {
            'base_date': timezone.localdate(),
            'starting_day': 5,
            'period_type': 'M',
            'base_currency': 'BRL'
        }
        form = InitialSetupForm(initial=initial_data)
    
    return render(request, 'finances/setup.html', {'form': form, 'version': VERSION})


@require_POST
def logout_view(request):
    """Faz logout do usuário."""
    auth_logout(request)
    return redirect('logout_success')


def logout_success_view(request):
    """Página de sucesso após o logout."""
    return render(request, 'finances/logged_out.html')


@login_required
def user_profile_view(request):
    """View and edit the user's profile (name, email, password)."""
    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    query_period = request.GET.get('period')
    start_date, end_date, _unused_period = get_current_period_dates(family, query_period)
    
    if request.method == 'POST':
        action = request.POST.get('action')

        # Block all profile editing in demo mode (except language change)
        from django.conf import settings
        if getattr(settings, 'DEMO_MODE', False) and action != 'change_language':
            messages.error(request, _('Profile editing is disabled in demo mode.'))
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/profile/{redirect_url}")

        if action == 'update_profile':
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()

            if username:
                UserModel = get_user_model()
                if UserModel.objects.filter(username=username).exclude(id=request.user.id).exists():
                    messages.error(request, _('This username is already taken.'))
                else:
                    request.user.username = username
                    request.user.email = email
                    request.user.save()
                    messages.success(request, _('Profile updated successfully.'))
            else:
                messages.error(request, _('Username cannot be empty.'))

        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if not request.user.check_password(current_password):
                messages.error(request, _('Current password is incorrect.'))
            elif len(new_password) < 6:
                messages.error(request, _('New password must be at least 6 characters long.'))
            elif new_password != confirm_password:
                messages.error(request, _('New passwords do not match.'))
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, _('Password changed successfully.'))

        elif action == 'change_language':
            language = request.POST.get('language', '').strip()
            valid_languages = ['en', 'pt-br']

            if language in valid_languages:
                request.user.language = language
                request.user.save()
                messages.success(request, _('Language preference updated successfully.'))
            else:
                messages.error(request, _('Invalid language selection.'))
        
        redirect_url = f"?period={query_period}" if query_period else ""
        return redirect(f"/profile/{redirect_url}")
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_member': current_member,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/profile.html', context)