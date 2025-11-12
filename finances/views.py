VERSION = "1.0.0-alpha4"

from django.core.management import call_command
import io
import shutil

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, Q
from django.db import transaction as db_transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse, FileResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import get_user_model, logout as auth_logout, login
from django.contrib import messages 
from django.utils import timezone
import json
from datetime import datetime as dt_datetime 
from decimal import Decimal
from .forms import InitialSetupForm  
from django.db.utils import OperationalError, ProgrammingError
from pathlib import Path
from django.conf import settings

import os
import traceback

from .version_utils import Version, needs_update

from .github_utils import (
    check_github_update, 
    requires_container_update,
    download_and_extract_release,
    create_database_backup
)

# NOVO: Import para Django-Money
from moneyed import Money

# Import Models
from .models import (
    Family, FamilyMember, FlowGroup, Transaction, Investment, FamilyConfiguration, ClosedPeriod, BankBalance, SystemVersion,
    FLOW_TYPE_INCOME, EXPENSE_MAIN, EXPENSE_SECONDARY, FLOW_TYPE_EXPENSE 
)
from .utils import (
    get_current_period_dates, 
    get_available_periods,
    check_period_change_impact, 
    close_current_period,
    copy_flow_groups_to_new_period,
    copy_previous_period_data,
    current_period_has_data
)

# Import Forms
from .forms import (
    FamilyConfigurationForm, FlowGroupForm, InvestmentForm, 
    AddMemberForm, NewUserAndMemberForm
)


def check_for_updates(request):
    """
    Checks for updates from both local scripts and GitHub releases.
    Priority: Local updates > GitHub updates
    """
    target_version = VERSION
    
    db_version = None
    try:
        db_version = SystemVersion.get_current_version()
    except (OperationalError, ProgrammingError):
        pass
    
    if db_version is None or db_version == '' or db_version.strip() == '':
        db_version = "0.0.0"
    
    # Check local updates first
    local_update_needed = False
    try:
        local_update_needed = needs_update(db_version, target_version)
    except ValueError:
        local_update_needed = True
    
    # If local updates exist, return local update info
    if local_update_needed:
        local_scripts = get_available_update_scripts(db_version, target_version)
        
        return JsonResponse({
            'needs_update': True,
            'update_type': 'local',
            'current_version': db_version,
            'target_version': target_version,
            'has_scripts': len(local_scripts) > 0,
            'update_scripts': local_scripts,
            'can_skip': False
        })
    
    # No local updates, check GitHub
    has_github_update, github_release = check_github_update(target_version)
    
    if has_github_update:
        github_version = github_release['version']
        container_required = requires_container_update(target_version, github_version)
        
        return JsonResponse({
            'needs_update': True,
            'update_type': 'github',
            'current_version': target_version,
            'target_version': github_version,
            'github_release': github_release,
            'requires_container': container_required,
            'can_skip': True
        })
    
    return JsonResponse({
        'needs_update': False,
        'current_version': target_version,
        'target_version': target_version
    })


@require_http_methods(["GET"])
def manual_check_updates(request):
    """
    Manual check for updates from settings page.
    Returns detailed info about available updates.
    """
    target_version = VERSION
    db_version = SystemVersion.get_current_version() or "0.0.0"
    
    # Check local
    local_update_needed = False
    try:
        local_update_needed = needs_update(db_version, target_version)
    except ValueError:
        local_update_needed = True
    
    # Check GitHub
    has_github_update, github_release = check_github_update(target_version)
    
    response_data = {
        'current_version': target_version,
        'db_version': db_version,
        'local_update_available': local_update_needed,
        'github_update_available': has_github_update,
    }
    
    if has_github_update:
        response_data['github_version'] = github_release['version']
        response_data['github_release'] = github_release
        response_data['requires_container'] = requires_container_update(
            target_version, 
            github_release['version']
        )
    
    return JsonResponse(response_data)


def get_available_update_scripts(from_version, to_version):
    """Finds update scripts that need to be run."""
    scripts_dir = Path(settings.BASE_DIR) / 'update_scripts'
    
    if not scripts_dir.exists():
        return []
    
    if from_version == "0.0.0":
        from_ver = Version("0.0.0")
    else:
        try:
            from_ver = Version(from_version)
        except ValueError:
            from_ver = Version("0.0.0")
    
    try:
        to_ver = Version(to_version)
    except ValueError:
        return []
    
    applicable_scripts = []
    
    for script_file in sorted(scripts_dir.glob('v*_*.py')):
        filename = script_file.name
        
        try:
            version_str = filename.split('_')[0][1:]
            script_version = Version(version_str)
            
            if from_ver < script_version <= to_ver:
                description = '_'.join(filename.split('_')[1:]).replace('.py', '').replace('_', ' ').title()
                
                applicable_scripts.append({
                    'filename': filename,
                    'version': version_str,
                    'description': description,
                    'path': str(script_file)
                })
        except (ValueError, IndexError):
            continue
    
    applicable_scripts.sort(key=lambda s: Version(s['version']))
    
    return applicable_scripts


def run_migrations():
    """
    Runs makemigrations and migrate commands.
    Returns (success, output)
    """
    try:
        output = io.StringIO()
        
        # Run makemigrations
        call_command('makemigrations', stdout=output, stderr=output, interactive=False)
        
        # Run migrate
        call_command('migrate', stdout=output, stderr=output, interactive=False)
        
        return True, output.getvalue()
    except Exception as e:
        return False, str(e)


@require_http_methods(["POST"])
def apply_local_updates(request):
    """
    Applies local updates: runs migrations and executes scripts.
    """
    try:
        data = json.loads(request.body)
        scripts = data.get('scripts', [])
        
        results = []
        all_success = True
        
        # ALWAYS run migrations first
        migration_success, migration_output = run_migrations()
        
        results.append({
            'script': 'Database Migrations',
            'version': VERSION,
            'status': 'success' if migration_success else 'error',
            'output': migration_output if migration_success else None,
            'error': migration_output if not migration_success else None
        })
        
        if not migration_success:
            all_success = False
        else:
            # Then run custom scripts
            for script_info in scripts:
                script_path = script_info['path']
                script_version = script_info['version']
                
                result = {
                    'script': script_info['filename'],
                    'version': script_version,
                    'status': 'pending'
                }
                
                try:
                    output = execute_update_script(script_path)
                    result['status'] = 'success'
                    result['output'] = output
                except Exception as e:
                    result['status'] = 'error'
                    result['error'] = str(e)
                    result['traceback'] = traceback.format_exc()
                    all_success = False
                    results.append(result)
                    break
                
                results.append(result)
        
        # Update version in DB if all successful
        if all_success:
            SystemVersion.set_version(VERSION)
        
        return JsonResponse({
            'success': all_success,
            'results': results,
            'new_version': VERSION if all_success else SystemVersion.get_current_version()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


def execute_update_script(script_path):
    """Executes an update script and returns output."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("update_script", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    if not hasattr(module, 'run'):
        raise ValueError(f"Script {script_path} must have a run() function")
    
    result = module.run()
    
    if not result.get('success', False):
        raise Exception(result.get('message', 'Script failed without message'))
    
    return result.get('message', 'Success')


@require_http_methods(["POST"])
def download_github_update(request):
    """
    Downloads and installs update from GitHub release.
    Then runs migrations and local scripts.
    """
    try:
        data = json.loads(request.body)
        zipball_url = data.get('zipball_url')
        target_version = data.get('target_version')
        
        if not zipball_url or not target_version:
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)
        
        # Download and extract
        success, message = download_and_extract_release(zipball_url)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': message
            })
        
        # Update version in DB
        SystemVersion.set_version(target_version)
        
        # IMPORTANT: After files are updated, need to reload
        # The frontend will trigger a reload which will then check for local updates
        
        return JsonResponse({
            'success': True,
            'message': message,
            'new_version': target_version,
            'needs_reload': True  # Signal to reload and check for local updates
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["POST"])
def create_backup(request):
    """Creates a database backup and returns download info."""
    try:
        success, message, backup_path = create_database_backup()
        
        if success and backup_path:
            return JsonResponse({
                'success': True,
                'message': message,
                'filename': backup_path.name,
                'download_url': f'/download-backup/{backup_path.name}/'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def download_backup(request, filename):
    """Downloads a database backup file."""
    try:
        backup_path = Path(settings.BASE_DIR) / 'backups' / filename
        
        if not backup_path.exists():
            return JsonResponse({'error': 'Backup file not found'}, status=404)
        
        # Security: only allow files in backups directory
        if not str(backup_path.resolve()).startswith(str(Path(settings.BASE_DIR) / 'backups')):
            return JsonResponse({'error': 'Invalid file path'}, status=403)
        
        response = FileResponse(open(backup_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def restore_backup(request):
    """
    Restores database from uploaded backup file.
    Returns family and user information from the backup.
    """
    try:
        if 'backup_file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No backup file provided'
            }, status=400)
        
        backup_file = request.FILES['backup_file']
        
        # Save uploaded file temporarily
        temp_path = Path(settings.BASE_DIR) / 'temp_restore.sqlite3'
        
        with open(temp_path, 'wb+') as destination:
            for chunk in backup_file.chunks():
                destination.write(chunk)
        
        # Read info from backup before restoring
        import sqlite3
        conn = sqlite3.connect(str(temp_path))
        cursor = conn.cursor()
        
        # Get family info
        cursor.execute("SELECT id, name FROM finances_family LIMIT 1")
        family_row = cursor.fetchone()
        
        family_info = None
        users_info = []
        
        if family_row:
            family_id, family_name = family_row
            family_info = {'id': family_id, 'name': family_name}
            
            # Get users
            cursor.execute("""
                SELECT u.username, u.email, fm.role 
                FROM finances_familymember fm
                JOIN finances_customuser u ON fm.user_id = u.id
                WHERE fm.family_id = ?
                ORDER BY fm.role, u.username
            """, (family_id,))
            
            for row in cursor.fetchall():
                users_info.append({
                    'username': row[0],
                    'email': row[1] or '',
                    'role': row[2]
                })
        
        conn.close()
        
        # Replace current database
        db_path = Path(settings.BASE_DIR) / 'db.sqlite3'
        if db_path.exists():
            backup_old = Path(settings.BASE_DIR) / 'db.sqlite3.old'
            shutil.copy2(db_path, backup_old)
        
        shutil.move(str(temp_path), str(db_path))
        
        return JsonResponse({
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': 'Database restored successfully'
        })
        
    except Exception as e:
        # Cleanup temp file on error
        temp_path = Path(settings.BASE_DIR) / 'temp_restore.sqlite3'
        if temp_path.exists():
            temp_path.unlink()
        
        return JsonResponse({
            'success': False,
            'error': f'Restore failed: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def skip_updates(request):
    """
    Skips updates and marks current version as target version.
    Only allowed for GitHub updates.
    """
    try:
        data = json.loads(request.body)
        update_type = data.get('update_type', 'local')
        
        if update_type == 'local':
            return JsonResponse({
                'success': False,
                'error': 'Local updates cannot be skipped'
            }, status=400)
        
        target_version = VERSION
        SystemVersion.set_version(target_version)
        
        return JsonResponse({
            'success': True,
            'new_version': target_version
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def initial_setup_view(request):
    """
    Initial setup view for first-time installation.
    Creates the first admin user, family, and configuration.
    Also handles database creation and migrations if needed.
    """
    
    # === STEP 1: Ensure database and tables exist ===
    try:
        UserModel = get_user_model()
        # Try to check if users exist
        users_exist = UserModel.objects.exists()
        
        # If users exist, redirect appropriately
        if users_exist:
            if request.user.is_authenticated:
                return redirect('dashboard')
            return redirect('auth_login')
            
    except OperationalError as e:
        # Database tables don't exist - need to run migrations
        if request.method != 'POST':
            # Show a loading message and run migrations
            context = {
                'needs_migration': True,
                'error_message': 'Database setup required. Running migrations...'
            }
            
            # Run migrations in the background
            try:
                # Capture output
                out = io.StringIO()
                
                # Run migrate command
                call_command('migrate', '--noinput', stdout=out, stderr=out)
                
                migration_output = out.getvalue()
                
                # Add success message
                context['migration_success'] = True
                context['migration_output'] = migration_output
                
            except Exception as migration_error:
                context['migration_error'] = str(migration_error)
            
            # Re-render the setup page (will now work with DB created)
            return render(request, 'finances/setup.html', {'form': InitialSetupForm(), **context})
    
    except Exception as e:
        # Other database errors
        messages.error(request, f"Database error: {str(e)}")
        context = {
            'form': InitialSetupForm(),
            'database_error': str(e)
        }
        return render(request, 'finances/setup.html', context)
    
    # === STEP 2: Handle form submission ===
    if request.method == 'POST':
        form = InitialSetupForm(request.POST)
        
        if form.is_valid():
            try:
                with db_transaction.atomic():
                    # 1. Create the admin user
                    UserModel = get_user_model()
                    admin_user = UserModel.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data.get('email', ''),
                        password=form.cleaned_data['password']
                    )
                    
                    # 2. Create the family
                    family = Family.objects.create(
                        name=form.cleaned_data['family_name']
                    )
                    
                    # 3. Create the family member (admin)
                    family_member = FamilyMember.objects.create(
                        user=admin_user,
                        family=family,
                        role='ADMIN'
                    )
                    
                    # 4. Create the family configuration
                    base_date = form.cleaned_data.get('base_date')
                    if not base_date:
                        base_date = timezone.localdate()
                    
                    base_currency = form.cleaned_data.get('base_currency', 'BRL')
                    
                    config = FamilyConfiguration.objects.create(
                        family=family,
                        starting_day=form.cleaned_data['starting_day'],
                        period_type=form.cleaned_data['period_type'],
                        base_date=base_date,
                        base_currency=base_currency
                    )
                    
                    # 5. Set system version
                    SystemVersion.set_version(VERSION)
                    
                    # 6. Log the user in
                    login(request, admin_user)
                    
                    # 7. Success message and redirect
                    messages.success(
                        request,
                        f"Welcome to SweetMoney! Your family '{family.name}' has been created successfully."
                    )
                    return redirect('dashboard')
                    
            except Exception as e:
                messages.error(
                    request,
                    f"An error occurred during setup: {str(e)}. Please try again."
                )
        else:
            # Form has validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # GET request - show empty form
        # Set default base_date to today
        initial_data = {
            'base_date': timezone.localdate(),
            'starting_day': 5,
            'period_type': 'M',
            'base_currency': 'BRL'
        }
        form = InitialSetupForm(initial=initial_data)
    
    return render(request, 'finances/setup.html', {'form': form, 'version': VERSION})


@login_required
def configuration_view(request):
    """View for family configuration settings."""
    try:
        member = FamilyMember.objects.select_related('family', 'family__configuration').get(user=request.user)
    except FamilyMember.DoesNotExist:
        messages.error(request, "You are not associated with any family.")
        return redirect('dashboard')
    
    if member.role not in ['ADMIN', 'PARENT']:
        messages.error(request, "Only Admins and Parents can access configuration.")
        return redirect('dashboard')
    
    family = member.family
    config = family.configuration
    
    # Get period info for navigation
    selected_period = request.GET.get('period')
    start_date, end_date, period_label = get_current_period_dates(family, selected_period)
    available_periods = get_available_periods(family)
    current_period_label = period_label
    
    if request.method == 'POST':
        form = FamilyConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            old_config = {
                'period_type': config.period_type,
                'starting_day': config.starting_day,
                'base_date': config.base_date
            }
            
            new_config = form.cleaned_data
            
            # Check if period configuration changed
            config_changed = (
                old_config['period_type'] != new_config['period_type'] or
                old_config['starting_day'] != new_config['starting_day'] or
                old_config['base_date'] != new_config['base_date']
            )
            
            if config_changed:
                # Check for data in current period
                has_data, data_count = check_period_change_impact(family, start_date, end_date)
                
                if has_data:
                    messages.warning(
                        request,
                        f"Period configuration updated. Your current period has {data_count} items. "
                        f"This period will be preserved as-is, and the new configuration will apply to future periods."
                    )
                    # Close current period before changing config
                    close_current_period(family, start_date, end_date, old_config['period_type'])
                else:
                    messages.info(request, "Period configuration updated. Changes will apply to the current and future periods.")
            
            form.save()
            messages.success(request, "Configuration updated successfully!")
            return redirect('configuration')
    else:
        form = FamilyConfigurationForm(instance=config)
    
    context = {
        'form': form,
        'family': family,
        'selected_period': selected_period,
        'start_date': start_date,
        'end_date': end_date,
        'period_label': period_label,
        'available_periods': available_periods,
        'current_period_label': current_period_label,
        'VERSION': VERSION,
        'app_version': VERSION,
    }
    
    return render(request, 'finances/configurations.html', context)


def get_family_context(user):
    """Retrieves the Family and FamilyMember context for the logged-in user."""
    try:
        family_member = FamilyMember.objects.select_related('family').get(user=user)
        family = family_member.family
        all_family_members = FamilyMember.objects.filter(family=family).select_related('user').order_by('user__username')
        return family, family_member, all_family_members
    except FamilyMember.DoesNotExist:
        return None, None, []

# === Utility Function for default Income Group ===
def get_default_income_flow_group(family, user, period_start_date):
    """Retrieves or creates the default income FlowGroup for the family and period."""
    # AJUSTE DJANGO-MONEY: Usar Money object ou deixar Django-money converter
    currency = family.configuration.base_currency if hasattr(family, 'configuration') else 'BRL'
    
    income_group, created = FlowGroup.objects.get_or_create(
        family=family,
        group_type=FLOW_TYPE_INCOME,
        period_start_date=period_start_date,
        defaults={
            'name': 'Income (Default)', 
            'budgeted_amount': Money(0, currency),  # AJUSTADO
            'owner': user
        }
    )
    return income_group

# === Utility function to check FlowGroup access ===
def can_access_flow_group(flow_group, family_member):
    if flow_group.owner == family_member.user:
        return True
    
    if family_member.role == 'ADMIN':
        return True
    
    # CRÍTICO: TODOS podem acessar Income (movido para cima)
    if flow_group.group_type == FLOW_TYPE_INCOME:
        return True
    
    if family_member.role == 'PARENT':
        if flow_group.is_shared:
            if flow_group.assigned_members.filter(id=family_member.id).exists():
                return True
        if flow_group.is_kids_group:
            return True
    
    if family_member.role == 'CHILD':
        if flow_group.is_kids_group and family_member in flow_group.assigned_children.all():
            return True
    
    return False

# === Get visible flow groups for dashboard (includes non-accessible for display only) ===
def get_visible_flow_groups_for_dashboard(family, family_member, period_start_date, group_type_filter=None):
    """
    Returns FlowGroups visible in the dashboard for the given family member.
    
    For PARENT/ADMIN: Shows ALL expense groups (owned, shared, and non-accessible)
    For CHILD: Shows only Kids groups assigned to them
    
    Returns tuple: (accessible_groups, display_only_groups)
    """
    base_query = FlowGroup.objects.filter(
        family=family,
        period_start_date=period_start_date
    )
    
    if group_type_filter:
        base_query = base_query.filter(group_type__in=group_type_filter)
    
    if family_member.role == 'CHILD':
        # Children see only Kids groups they're assigned to (all accessible)
        accessible_groups = base_query.filter(
            Q(is_kids_group=True, assigned_children=family_member)
        ).distinct()
        display_only_groups = FlowGroup.objects.none()
    else:
        # Parents/Admins see ALL expense groups
        all_groups = base_query.all()
        
        # Separate accessible from display-only
        accessible_ids = []
        display_only_ids = []
        
        for group in all_groups:
            if can_access_flow_group(group, family_member):
                accessible_ids.append(group.id)
            else:
                display_only_ids.append(group.id)
        
        accessible_groups = base_query.filter(id__in=accessible_ids)
        display_only_groups = base_query.filter(id__in=display_only_ids)
    
    return accessible_groups, display_only_groups

# === NEW: Get visible flow groups for editing ===
def get_visible_flow_groups(family, family_member, period_start_date, group_type_filter=None):
    """
    Returns FlowGroups visible to the given family member for the specified period.
    
    Visibility rules:
    - Own groups (always visible)
    - Shared groups (visible to assigned Admins/Parents only)
    - Kids groups (visible to assigned children, and to all Admins/Parents)
    - Admins can see ALL groups
    """
    base_query = FlowGroup.objects.filter(
        family=family,
        period_start_date=period_start_date
    )
    
    if group_type_filter:
        base_query = base_query.filter(group_type__in=group_type_filter)
    
    if family_member.role == 'CHILD':
        # Children see only Kids groups they're assigned to
        visible_groups = base_query.filter(
            Q(is_kids_group=True, assigned_children=family_member)
        )
    elif family_member.role == 'ADMIN':
        # Admins see ALL groups
        visible_groups = base_query.all()
    else:
        # Parents see:
        # 1. Their own groups (non-shared)
        # 2. Shared groups they're assigned to
        # 3. All Kids groups
        visible_groups = base_query.filter(
            Q(owner=family_member.user) |  # Own groups
            Q(is_shared=True, assigned_members=family_member) |  # Shared groups (assigned)
            Q(is_kids_group=True)  # Kids groups (all)
        )
    
    return visible_groups.distinct()

# === Utility Wrapper for Period Context ===
def get_base_template_context(family, query_period, start_date):
    """
    Gets the context required by base.html (period selector with current period label).
    Adds VERSION to context.
    """
    # Get available periods
    available_periods = get_available_periods(family)
    
    # Find current period label based on query_period or current date
    current_period_label = None
    current_period_value = query_period if query_period else start_date.strftime("%Y-%m-%d")
    
    for period in available_periods:
        if period['value'] == current_period_value:
            period['is_current'] = True
            current_period_label = period['label']
        else:
            period['is_current'] = False
    
    # If no match found, use the first period (current)
    if not current_period_label and available_periods:
        available_periods[0]['is_current'] = True
        current_period_label = available_periods[0]['label']
    
    return {
        'available_periods': available_periods,
        'current_period_label': current_period_label,
        'selected_period': current_period_value,
        'app_version': VERSION,
    }

# === Utility Function for Default Date ===
def get_default_date_for_period(start_date, end_date):
    """
    Returns the appropriate default date for data entry.
    If the period includes today, return today.
    If it's a past period, return the start date.
    If it's a future period, return the start date.
    """
    today = timezone.localdate()
    
    if start_date <= today <= end_date:
        # Current period - use today
        return today
    else:
        # Past or future period - use start date
        return start_date

# === NEW: Get periods history for bar chart ===
def get_periods_history(family, current_period_start):
    """
    Returns the last 12 periods with total expenses for bar chart.
    Includes dynamic bar colors based on income commitment %.
    Returns dict with 'labels', 'values', 'colors', 'avg_savings', and 'trend'.
    ONLY INCLUDES PERIODS WITH DATA.
    """
    available_periods = get_available_periods(family)
    
    # Get up to 12 most recent periods that have data
    periods_to_show = []
    savings_values = []
    
    for period in available_periods[:24]:  # Look at more periods to find 12 with data
        period_start = period['start_date']
        period_end = period['end_date']
        
        # Check if period has any transaction data
        has_data = Transaction.objects.filter(
            flow_group__family=family,
            date__range=(period_start, period_end)
        ).exists()
        
        # Skip periods without data
        if not has_data:
            continue
        
        # Calculate total realized expenses
        total_expenses = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type__in=FLOW_TYPE_EXPENSE,
            date__range=(period_start, period_end),
            realized=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Calculate total realized income
        total_income = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(period_start, period_end),
            realized=True,
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Add Kids groups realized budgets to expenses
        kids_realized = FlowGroup.objects.filter(
            family=family,
            period_start_date=period_start,
            is_kids_group=True,
            realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')
        
        total_expenses += kids_realized
        
        # AJUSTE DJANGO-MONEY: Converter Money para float para cálculos
        if hasattr(total_expenses, 'amount'):
            total_expenses_float = float(total_expenses.amount)
        else:
            total_expenses_float = float(total_expenses)
            
        if hasattr(total_income, 'amount'):
            total_income_float = float(total_income.amount)
        else:
            total_income_float = float(total_income)
        
        # Calculate commitment percentage
        commitment_pct = 0
        if total_income_float > 0:
            commitment_pct = (total_expenses_float / total_income_float * 100)
        
        # Determine bar color based on commitment
        if commitment_pct >= 98:
            bar_color = 'rgb(239, 68, 68)'  # Red
        elif commitment_pct >= 90:
            bar_color = 'rgb(249, 115, 22)'  # Orange
        else:
            bar_color = 'rgb(134, 239, 172)'  # Light green
        
        # Calculate savings (income - expenses)
        savings = total_income_float - total_expenses_float
        savings_values.append(savings)
        
        periods_to_show.append({
            'label': period['label'],
            'value': total_expenses_float,
            'color': bar_color,
            'savings': savings
        })
        
        # Stop if we have 12 periods
        if len(periods_to_show) >= 12:
            break
    
    # Reverse to show oldest to newest (left to right)
    periods_to_show.reverse()
    savings_values.reverse()
    
    # Calculate average savings
    avg_savings = sum(savings_values) / len(savings_values) if savings_values else 0
    
    # Calculate trend (compare first half vs second half)
    trend = 'stable'
    if len(periods_to_show) >= 6:
        half_point = len(periods_to_show) // 2
        first_half_avg = sum(p['value'] for p in periods_to_show[:half_point]) / half_point
        second_half_avg = sum(p['value'] for p in periods_to_show[half_point:]) / (len(periods_to_show) - half_point)
        
        # If second half is 5% or more higher, trend is up
        if second_half_avg > first_half_avg * 1.05:
            trend = 'up'
        # If second half is 5% or more lower, trend is down
        elif second_half_avg < first_half_avg * 0.95:
            trend = 'down'
    
    return {
        'labels': [p['label'] for p in periods_to_show],
        'values': [p['value'] for p in periods_to_show],
        'colors': [p['color'] for p in periods_to_show],
        'avg_savings': avg_savings,
        'trend': trend
    }

# === Core Views ===

@login_required
def dashboard_view(request):
    family, current_member, family_members = get_family_context(request.user)
    from decimal import Decimal, ROUND_DOWN
    if not family:
        return render(request, 'finances/setup.html') 

    query_period = request.GET.get('period')
    start_date, end_date, current_period_label = get_current_period_dates(family, query_period)
    
    # Get historical role for this period
    from .utils import get_member_role_for_period
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    expense_group_q = Q(group_type=EXPENSE_MAIN) | Q(group_type=EXPENSE_SECONDARY)
    
    # Get visible expense groups based on HISTORICAL role
    accessible_expense_groups, display_only_expense_groups = get_visible_flow_groups_for_dashboard(
        family, 
        current_member, 
        start_date, 
        group_type_filter=FLOW_TYPE_EXPENSE
    )
    
    # Annotate accessible groups
    accessible_expense_groups = accessible_expense_groups.annotate(
        total_estimated=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        ),
        total_spent=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date), transactions__realized=True)
        )
    ).order_by('order', 'name')
    
    # Annotate display-only groups (for Parents/Admins to see in dashboard)
    display_only_expense_groups = display_only_expense_groups.annotate(
        total_estimated=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        ),
        total_spent=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date), transactions__realized=True)
        )
    ).order_by('order', 'name')
    
    # Process accessible groups
    budgeted_expense = Decimal(0.00)
    for group in accessible_expense_groups:
        # AJUSTE DJANGO-MONEY: Extrair valor numérico de Money object
        if hasattr(group.total_estimated, 'amount'):
            group.total_estimated = Decimal(str(group.total_estimated.amount))
        else:
            group.total_estimated = (group.total_estimated if group.total_estimated is not None else Decimal('0.00'))
        
        if hasattr(group.total_spent, 'amount'):
            group.total_spent = Decimal(str(group.total_spent.amount))
        else:
            group.total_spent = (group.total_spent if group.total_spent is not None else Decimal('0.00'))
        
        group.total_estimated = group.total_estimated.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = group.total_spent.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = True  # Mark as accessible
        
        # For Kids groups shown to Parents/Admins, calculate child expenses
        if group.is_kids_group and member_role_for_period in ['ADMIN', 'PARENT']:
            child_exp = Transaction.objects.filter(
                flow_group=group,
                date__range=(start_date, end_date)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # AJUSTE DJANGO-MONEY
            if hasattr(child_exp, 'amount'):
                group.child_expenses = Decimal(str(child_exp.amount))
            else:
                group.child_expenses = child_exp
            
            # Mark if this group was created by a child (owner is a child)
            group.is_child_group = False
            if group.owner:
                owner_member = FamilyMember.objects.filter(user=group.owner, family=family).first()
                if owner_member and owner_member.role == 'CHILD':
                    group.is_child_group = True
        
        # AJUSTE DJANGO-MONEY: Extrair budgeted_amount
        budgeted_amt = group.budgeted_amount
        if hasattr(budgeted_amt, 'amount'):
            budgeted_amt = Decimal(str(budgeted_amt.amount))
        else:
            budgeted_amt = Decimal(str(budgeted_amt))
        
        # Check if estimated exceeds budget
        group.budget_warning = group.total_estimated > budgeted_amt
        group.total_estimated = group.total_estimated if group.total_estimated > budgeted_amt else budgeted_amt
        
        # Only add to budgeted_expense if it's NOT a child's own group
        is_child_own_group = False
        if group.owner:
            owner_member = FamilyMember.objects.filter(user=group.owner, family=family).first()
            if owner_member and owner_member.role == 'CHILD':
                is_child_own_group = True
        
        if not is_child_own_group:
            budgeted_expense = group.total_estimated + budgeted_expense

        
    
    # Process display-only groups (for Parents/Admins)
    for group in display_only_expense_groups:
        # AJUSTE DJANGO-MONEY: Extrair valor numérico
        if hasattr(group.total_estimated, 'amount'):
            group.total_estimated = Decimal(str(group.total_estimated.amount))
        else:
            group.total_estimated = (group.total_estimated if group.total_estimated is not None else Decimal('0.00'))
        
        if hasattr(group.total_spent, 'amount'):
            group.total_spent = Decimal(str(group.total_spent.amount))
        else:
            group.total_spent = (group.total_spent if group.total_spent is not None else Decimal('0.00'))
        
        group.total_estimated = group.total_estimated.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = group.total_spent.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = False  # Mark as NOT accessible
        
        # AJUSTE DJANGO-MONEY: Extrair budgeted_amount
        budgeted_amt = group.budgeted_amount
        if hasattr(budgeted_amt, 'amount'):
            budgeted_amt = Decimal(str(budgeted_amt.amount))
        else:
            budgeted_amt = Decimal(str(budgeted_amt))
        
        # Check if estimated exceeds budget
        group.budget_warning = group.total_estimated > budgeted_amt
        group.total_estimated = group.total_estimated if group.total_estimated > budgeted_amt else budgeted_amt
        
        # Add to budgeted_expense
        budgeted_expense = group.total_estimated + budgeted_expense
    
    # Combine accessible and display-only groups for template
    expense_groups = list(accessible_expense_groups) + list(display_only_expense_groups)

    # Income calculation differs based on HISTORICAL role
    if member_role_for_period == 'CHILD':
        # === CHILDREN VIEW ===
        kids_groups = FlowGroup.objects.filter(
            family=family,
            period_start_date=start_date,
            is_kids_group=True,
            assigned_children=current_member
        )
        
        kids_income_entries = []
        budgeted_income = Decimal('0.00')
        realized_income = Decimal('0.00')
        
        for kids_group in kids_groups:
            # AJUSTE DJANGO-MONEY: Extrair budgeted_amount
            budg_amt = kids_group.budgeted_amount
            if hasattr(budg_amt, 'amount'):
                budg_amt = Decimal(str(budg_amt.amount))
            else:
                budg_amt = Decimal(str(budg_amt))
            
            kids_income_entries.append({
                'id': f'kids_{kids_group.id}',
                'description': kids_group.name,
                'amount': budg_amt.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'date': start_date,
                'realized': kids_group.realized,
                'is_kids_income': True,
                'kids_group_id': kids_group.id,
                'member': current_member,
            })
            budgeted_income += budg_amt
            if kids_group.realized:
                realized_income += budg_amt
        
        income_group = get_default_income_flow_group(family, request.user, start_date)
        manual_income_transactions = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).select_related('member__user').order_by('-date', 'order')
        
        for trans in manual_income_transactions:
            # AJUSTE DJANGO-MONEY
            amt = trans.amount
            if hasattr(amt, 'amount'):
                amt = Decimal(str(amt.amount))
            else:
                amt = Decimal(str(amt))
            
            budgeted_income += amt
            if trans.realized:
                realized_income += amt
        
        recent_income_transactions = list(manual_income_transactions)
        income_flow_group_id = income_group.id
        context_kids_income = kids_income_entries

        realized_exp = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups,
            date__range=(start_date, end_date),
            realized=True,
            is_child_expense=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(realized_exp, 'amount'):
            realized_expense = Decimal(str(realized_exp.amount))
        else:
            realized_expense = realized_exp
        
    else:
        # === PARENTS/ADMINS VIEW ===
        income_group = get_default_income_flow_group(family, request.user, start_date)
        
        recent_income_transactions = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            is_child_manual_income=False
        ).select_related('member__user').order_by('-date', 'order')
        
        income_flow_group_id = income_group.id
        
        budg_inc = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(budg_inc, 'amount'):
            budgeted_income = Decimal(str(budg_inc.amount))
        else:
            budgeted_income = budg_inc
        
        real_inc = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            realized=True,
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(real_inc, 'amount'):
            realized_income = Decimal(str(real_inc.amount))
        else:
            realized_income = real_inc
        
        kids_realized_sum = FlowGroup.objects.filter(
            family=family,
            period_start_date=start_date,
            is_kids_group=True,
            realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(kids_realized_sum, 'amount'):
            kids_groups_realized_budget = Decimal(str(kids_realized_sum.amount))
        else:
            kids_groups_realized_budget = kids_realized_sum
            
        children_manual_income = {}
        for child in family_members:
            if child.role == 'CHILD':
                child_income = Transaction.objects.filter(
                    flow_group=income_group,
                    date__range=(start_date, end_date),
                    member=child,
                    is_child_manual_income=True
                )
                
                if child_income.exists():
                    tot = child_income.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    real_tot = child_income.filter(realized=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    # AJUSTE DJANGO-MONEY
                    if hasattr(tot, 'amount'):
                        tot = Decimal(str(tot.amount))
                    if hasattr(real_tot, 'amount'):
                        real_tot = Decimal(str(real_tot.amount))
                    
                    children_manual_income[child.id] = {
                        'member': child,
                        'total': tot,
                        'realized_total': real_tot,
                        'transactions': list(child_income.values('description', 'amount', 'date', 'realized'))
                    }
        
        context_kids_income = []
        
        realized_exp_calc = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups,
            date__range=(start_date, end_date),
            realized=True,
            is_child_expense=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(realized_exp_calc, 'amount'):
            realized_expense = Decimal(str(realized_exp_calc.amount))
        else:
            realized_expense = realized_exp_calc
        
        realized_expense += kids_groups_realized_budget

    
    summary_totals = {
        'total_budgeted_income': (budgeted_income).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_realized_income': (realized_income).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_budgeted_expense': (budgeted_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_realized_expense': (realized_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'estimated_result': (budgeted_income - budgeted_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'realized_result': (realized_income - realized_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
    }

    default_date = get_default_date_for_period(start_date, end_date)
    
    child_can_create_groups = False
    if member_role_for_period == 'CHILD':
        child_manual_sum = Transaction.objects.filter(
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(child_manual_sum, 'amount'):
            child_manual_income_total = Decimal(str(child_manual_sum.amount))
        else:
            child_manual_income_total = child_manual_sum
        
        child_can_create_groups = child_manual_income_total > Decimal('0.00')

    # Get periods history for bar chart
    periods_history = get_periods_history(family, start_date)

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_period_label': current_period_label,
        'expense_groups': expense_groups,
        'recent_income_transactions': recent_income_transactions,
        'income_flow_group_id': income_flow_group_id,
        'family_members': family_members,
        'current_member': current_member,
        'member_role_for_period': member_role_for_period,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'summary_totals': summary_totals,
        'child_can_create_groups': child_can_create_groups,
        'kids_income_entries': context_kids_income if member_role_for_period == 'CHILD' else [],
        'children_manual_income': children_manual_income if member_role_for_period in ['ADMIN', 'PARENT'] else {},
        'periods_history_json': json.dumps(periods_history),
    }
    
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/dashboard.html', context)

@login_required
def bank_reconciliation_view(request):
    """
    Bank reconciliation view.
    Allows users to input bank balances and compare with calculated balances.
    """
    from decimal import Decimal, ROUND_DOWN
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    start_date, end_date, current_period_label = get_current_period_dates(family, query_period)
    
    # Get member role for period
    from .utils import get_member_role_for_period
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    # Get mode from query param (detailed or general)
    mode = request.GET.get('mode', 'general')  # 'general' or 'detailed'
    
    # Get existing bank balances for this period
    bank_balances = BankBalance.objects.filter(
        family=family,
        period_start_date=start_date
    ).order_by('member', '-date')
    
    # Calculate income and expenses for the period
    income_transactions = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__period_start_date=start_date,
        flow_group__group_type=FLOW_TYPE_INCOME,
        date__gte=start_date,
        date__lte=end_date,
        realized=True
    )
    
    expense_transactions = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__period_start_date=start_date,
        flow_group__group_type__in=[EXPENSE_MAIN, EXPENSE_SECONDARY],
        date__gte=start_date,
        date__lte=end_date,
        realized=True
    ).exclude(
        flow_group__is_investment=True  # Exclude investment groups
    )
    
    if mode == 'general':
        # General reconciliation - family totals
        tot_inc = income_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        tot_exp = expense_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(tot_inc, 'amount'):
            total_income = Decimal(str(tot_inc.amount))
        else:
            total_income = tot_inc
            
        if hasattr(tot_exp, 'amount'):
            total_expenses = Decimal(str(tot_exp.amount))
        else:
            total_expenses = tot_exp
        
        calculated_balance = total_income - total_expenses
        
        # Get total bank balance
        tot_bank = bank_balances.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(tot_bank, 'amount'):
            total_bank_balance = Decimal(str(tot_bank.amount))
        else:
            total_bank_balance = tot_bank
        
        # Calculate discrepancy
        discrepancy = total_bank_balance - calculated_balance
        discrepancy_percentage = abs(discrepancy / calculated_balance * 100) if calculated_balance != 0 else 0
        has_warning = discrepancy_percentage > 5
        
        reconciliation_data = {
            'mode': 'general',
            'total_income': total_income,
            'total_expenses': total_expenses.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'calculated_balance': calculated_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'total_bank_balance': total_bank_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'discrepancy': discrepancy.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'discrepancy_percentage': discrepancy_percentage.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'has_warning': has_warning,
        }
    else:
        # Detailed reconciliation - by member
        members_data = []
        
        for member in family_members:
            # Income for this member
            mem_inc = income_transactions.filter(member=member).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Expenses for this member
            mem_exp = expense_transactions.filter(member=member).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # AJUSTE DJANGO-MONEY
            if hasattr(mem_inc, 'amount'):
                member_income = Decimal(str(mem_inc.amount))
            else:
                member_income = mem_inc
                
            if hasattr(mem_exp, 'amount'):
                member_expenses = Decimal(str(mem_exp.amount))
            else:
                member_expenses = mem_exp
            
            # Calculated balance for member
            member_calculated_balance = member_income - member_expenses
            
            # Bank balance for member
            mem_bank = bank_balances.filter(member=member).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # AJUSTE DJANGO-MONEY
            if hasattr(mem_bank, 'amount'):
                member_bank_balance = Decimal(str(mem_bank.amount))
            else:
                member_bank_balance = mem_bank
            
            # Discrepancy
            member_discrepancy = member_bank_balance - member_calculated_balance
            member_discrepancy_percentage = abs(member_discrepancy / member_calculated_balance * 100) if member_calculated_balance != 0 else 0
            member_has_warning = member_discrepancy_percentage > 5
            
            members_data.append({
                'member': member,
                'income': member_income.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'expenses': member_expenses.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'calculated_balance': member_calculated_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'bank_balance': member_bank_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'discrepancy': member_discrepancy.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'discrepancy_percentage': member_discrepancy_percentage.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'has_warning': member_has_warning,
            })
        
        reconciliation_data = {
            'mode': 'detailed',
            'members_data': members_data,
        }
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'bank_balances': bank_balances,
        'family_members': family_members,
        'member_role_for_period': member_role_for_period,
        'reconciliation_data': reconciliation_data,
        'mode': mode,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/bank_reconciliation.html', context)


# === AJAX Endpoints ===

@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_items_ajax(request):
    """
    Handles AJAX request to reorder Transactions within a FlowGroup.
    Receives array of {id, order} objects and updates the order field.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        data = json.loads(request.body)
        items_data = data.get('items', [])
        
        if not items_data:
            return JsonResponse({'error': 'No items data provided.'}, status=400)
        
        # Update each transaction's order
        for item_data in items_data:
            item_id = item_data.get('id')
            new_order = item_data.get('order')
            
            if item_id and new_order is not None:
                transaction = Transaction.objects.filter(
                    id=item_id,
                    flow_group__family=family
                ).first()
                
                if transaction:
                    # Check if user has permission to reorder
                    flow_group = transaction.flow_group
                    if can_access_flow_group(flow_group, current_member):
                        transaction.order = new_order
                        transaction.save(update_fields=['order'])
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)



@login_required
@require_POST
@db_transaction.atomic
def save_flow_item_ajax(request):
    """
    Handles AJAX request to save or update a Transaction.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")

    try:
        data = json.loads(request.body)
        
        flow_group_id = data.get('flow_group_id')
        transaction_id = data.get('transaction_id') 
        description = data.get('description')
        amount_str = data.get('amount')
        date_str = data.get('date')
        member_id = data.get('member_id')
        realized = data.get('realized', False)
        is_child_manual = data.get('is_child_manual', False)
        is_child_expense = data.get('is_child_expense', False)
        
        # Basic validation
        if not all([flow_group_id, description, amount_str, date_str]):
            return JsonResponse({'error': 'Missing required fields.'}, status=400)
            
        amount = Decimal(amount_str)
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        
        # Check access permissions
        if not can_access_flow_group(flow_group, current_member):
            return HttpResponseForbidden("You don't have permission to edit this group.")

        # AJUSTE DJANGO-MONEY: Pegar moeda da família
        currency = family.configuration.base_currency

        if transaction_id and transaction_id != '0' and transaction_id is not None:
            transaction = get_object_or_404(Transaction, id=transaction_id, flow_group=flow_group)
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
                transaction.member = member
        else:
            max_order = Transaction.objects.filter(flow_group=flow_group).aggregate(max_order=Max('order'))['max_order']
            new_order = (max_order or 0) + 1
            transaction = Transaction(
                flow_group=flow_group,
                order=new_order
            )
            
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
            else:
                member = current_member
            
            transaction.member = member

        transaction.description = description
        # AJUSTE DJANGO-MONEY: Criar Money object com moeda correta
        transaction.amount = Money(abs(amount), currency)
        transaction.date = date
        transaction.realized = realized
        
        # Set is_child_manual_income flag if this is a manual income by a CHILD
        if is_child_manual and current_member.role == 'CHILD' and flow_group.group_type == FLOW_TYPE_INCOME:
            transaction.is_child_manual_income = True

        if is_child_expense and current_member.role == 'CHILD' and flow_group.group_type != FLOW_TYPE_INCOME:
            transaction.is_child_expense = True
        
        transaction.save()

        # AJUSTE DJANGO-MONEY: Retornar só o valor numérico
        amount_value = str(transaction.amount.amount) if hasattr(transaction.amount, 'amount') else str(transaction.amount)

        return JsonResponse({
            'status': 'success',
            'transaction_id': transaction.id,
            'description': transaction.description,
            'amount': amount_value,
            'date': transaction.date.strftime('%Y-%m-%d'),
            'member_id': transaction.member.id,
            'member_name': transaction.member.user.username,
            'realized': transaction.realized,
        })

    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def delete_flow_item_ajax(request):
    """Handles AJAX request to delete a single Transaction item."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")

    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return JsonResponse({'error': 'Missing transaction_id.'}, status=400)

        transaction = get_object_or_404(Transaction, id=transaction_id, flow_group__family=family)
        
        # Check access permissions
        if not can_access_flow_group(transaction.flow_group, current_member):
            return HttpResponseForbidden("You don't have permission to delete from this group.")
        
        transaction.delete()

        return JsonResponse({'status': 'success', 'transaction_id': transaction_id})

    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def toggle_kids_group_realized_ajax(request):
    """
    Handles AJAX request to toggle FlowGroup.realized for Kids groups.
    Only Parents and Admins can toggle this.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    # Only Parents and Admins can toggle
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Parents and Admins can mark Kids groups as realized.")
    
    try:
        data = json.loads(request.body)
        flow_group_id = data.get('flow_group_id')
        new_realized_status = data.get('realized', False)
        
        if not flow_group_id:
            return JsonResponse({'error': 'Missing flow_group_id.'}, status=400)
        
        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        
        # Must be a Kids group
        if not flow_group.is_kids_group:
            return JsonResponse({'error': 'Can only toggle realized for Kids groups.'}, status=400)
        
        # Update realized status
        flow_group.realized = new_realized_status
        flow_group.save()
        
        # AJUSTE DJANGO-MONEY: Extrair valor numérico
        budget_value = str(flow_group.budgeted_amount.amount) if hasattr(flow_group.budgeted_amount, 'amount') else str(flow_group.budgeted_amount)
        
        return JsonResponse({
            'status': 'success',
            'flow_group_id': flow_group.id,
            'realized': flow_group.realized,
            'budget': budget_value
        })
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_groups_ajax(request):
    """
    Handles AJAX request to reorder FlowGroups.
    Receives array of {id, order} objects and updates the order field.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        data = json.loads(request.body)
        groups_data = data.get('groups', [])
        
        if not groups_data:
            return JsonResponse({'error': 'No groups data provided.'}, status=400)
        
        # Update each group's order
        for group_data in groups_data:
            group_id = group_data.get('id')
            new_order = group_data.get('order')
            
            if group_id and new_order is not None:
                flow_group = FlowGroup.objects.filter(
                    id=group_id,
                    family=family
                ).first()
                
                if flow_group:
                    # Check if user has permission to reorder
                    # Only accessible groups can be reordered
                    if can_access_flow_group(flow_group, current_member):
                        flow_group.order = new_order
                        flow_group.save(update_fields=['order'])
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


# === Delete Flow Group View ===
@login_required
@require_POST
@db_transaction.atomic
def delete_flow_group_view(request, group_id):
    """
    Deletes a FlowGroup and all its transactions.
    """
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    try:
        flow_group = get_object_or_404(FlowGroup, id=group_id, family=family)
        
        # Only owner or admin can delete
        if flow_group.owner != request.user and current_member.role != 'ADMIN':
            return JsonResponse({'error': 'Permission denied.'}, status=403)
        
        group_name = flow_group.name
        
        # Delete the group (CASCADE will delete all transactions)
        flow_group.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f"Flow Group '{group_name}' and all its data have been deleted."
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@db_transaction.atomic
def copy_previous_period_ajax(request):
    """
    Copies all data from previous period to current period.
    Excludes child-created data.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    # Only admins and parents can copy period data
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Admins and Parents can copy period data.")
    
    try:
        # Check if current period already has data
        if current_period_has_data(family):
            return JsonResponse({
                'error': 'Current period already has data. Cannot copy.'
            }, status=400)
        
        # Copy data
        result = copy_previous_period_data(family, exclude_child_data=True)
        
        return JsonResponse({
            'status': 'success',
            'groups_copied': result['groups_copied'],
            'transactions_copied': result['transactions_copied'],
            'message': f"Copied {result['groups_copied']} groups and {result['transactions_copied']} transactions from previous period."
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error copying period: {str(e)}'}, status=500)


@login_required
def check_period_empty_ajax(request):
    """
    Checks if current period is empty (for showing copy button).
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        has_data = current_period_has_data(family)
        
        return JsonResponse({
            'status': 'success',
            'has_data': has_data,
            'can_copy': not has_data and current_member.role in ['ADMIN', 'PARENT']
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error checking period: {str(e)}'}, status=500)




# === Logout View ===
@require_POST
def logout_view(request):
    """
    Logs out the user and redirects to logout success page.
    Only accepts POST requests for security.
    """
    auth_logout(request)
    return redirect('logout_success')


# === Logout Success View ===
def logout_success_view(request):
    """
    Shows logout success page (no authentication required).
    """
    return render(request, 'finances/logged_out.html')


# === User Profile View ===
@login_required
def user_profile_view(request):
    """
    View and edit user profile (username, email, password).
    """
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            
            if username:
                UserModel = get_user_model()
                # Check if username is taken by another user
                if UserModel.objects.filter(username=username).exclude(id=request.user.id).exists():
                    messages.error(request, 'This username is already taken.')
                else:
                    request.user.username = username
                    request.user.email = email
                    request.user.save()
                    messages.success(request, 'Profile updated successfully.')
            else:
                messages.error(request, 'Username cannot be empty.')
        
        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_password) < 6:
                messages.error(request, 'New password must be at least 6 characters long.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                # Re-login user to maintain session
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully.')
        
        # Preserve period in redirect
        redirect_url = f"?period={query_period}" if query_period else ""
        return redirect(f"/profile/{redirect_url}")
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_member': current_member,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/profile.html', context)


@login_required
def create_flow_group_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    # Get period from query parameter (critical for maintaining selected period)
    query_period = request.GET.get('period') or request.POST.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)

    if request.method == 'POST':
        form = FlowGroupForm(request.POST, family=family)
        if form.is_valid():
            flow_group = form.save(commit=False)
            flow_group.family = family
            flow_group.owner = request.user
            flow_group.group_type = EXPENSE_MAIN
            # CRITICAL: Use the period from query/POST parameter, not current date
            flow_group.period_start_date = start_date
            
            # Validation for CHILD users: budget cannot exceed manual income
            if current_member.role == 'CHILD':
                # Calculate child's manual income total for this period
                child_manual_sum = Transaction.objects.filter(
                    flow_group__group_type=FLOW_TYPE_INCOME,
                    flow_group__family=family,
                    date__range=(start_date, end_date),
                    member=current_member,
                    is_child_manual_income=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                # AJUSTE DJANGO-MONEY
                if hasattr(child_manual_sum, 'amount'):
                    child_manual_income_total = Decimal(str(child_manual_sum.amount))
                else:
                    child_manual_income_total = child_manual_sum
                
                # AJUSTE DJANGO-MONEY: Extrair budgeted_amount
                budg_amt = flow_group.budgeted_amount
                if hasattr(budg_amt, 'amount'):
                    budg_amt_val = Decimal(str(budg_amt.amount))
                else:
                    budg_amt_val = Decimal(str(budg_amt))
                
                if budg_amt_val > child_manual_income_total:
                    messages.error(request, f"Budget cannot exceed your available balance (${child_manual_income_total}). Please enter a budget of ${child_manual_income_total} or less.")
                    context = {
                        'form': form,
                        'start_date': start_date,
                        'end_date': end_date,
                        'current_member': current_member,
                        'child_max_budget': child_manual_income_total,
                    }
                    context.update(get_base_template_context(family, query_period, start_date))
                    return render(request, 'finances/add_flow_group.html', context)
                
                # CHILD FlowGroups are automatically shared with all Parents/Admins
                flow_group.is_shared = True
            
            # If Kids group is checked, automatically enable shared
            if flow_group.is_kids_group:
                flow_group.is_shared = True
            
            flow_group.save()
            
            # If CHILD created the group, auto-assign all Parents/Admins
            if current_member.role == 'CHILD':
                parents_admins = FamilyMember.objects.filter(
                    family=family,
                    role__in=['ADMIN', 'PARENT']
                )
                flow_group.assigned_members.set(parents_admins)
            else:
                # Save assigned members/children (ManyToMany field)
                form.save_m2m()
            
            messages.success(request, f"Flow Group '{flow_group.name}' created for period starting {start_date.strftime('%B %d, %Y')}.")
            # Preserve period in redirect
            redirect_url = f"?period={start_date.strftime('%Y-%m-%d')}"
            return redirect(f"/flow-group/{flow_group.id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm(family=family)

    # Get default date for this period
    default_date = get_default_date_for_period(start_date, end_date)
    
    # Calculate max budget for child users
    child_max_budget = None
    if current_member.role == 'CHILD':
        child_sum = Transaction.objects.filter(
            flow_group__group_type=FLOW_TYPE_INCOME,
            flow_group__family=family,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # AJUSTE DJANGO-MONEY
        if hasattr(child_sum, 'amount'):
            child_max_budget = Decimal(str(child_sum.amount))
        else:
            child_max_budget = child_sum

    context = {
        'form': form,
        'is_new': True,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'start_date': start_date,
        'end_date': end_date,
        'child_max_budget': child_max_budget,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def edit_flow_group_view(request, group_id):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
        
    group = get_object_or_404(FlowGroup, id=group_id, family=family)
    
    # Check access permissions
    if not can_access_flow_group(group, current_member):
        messages.error(request, "You don't have permission to access this group.")
        return redirect('dashboard')
    
    # Get period from query parameter, or use the group's period
    query_period = request.GET.get('period')
    if not query_period:
        # Use the FlowGroup's period_start_date as the default
        query_period = group.period_start_date.strftime('%Y-%m-%d')
    
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    from .utils import get_member_role_for_period
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    
    # Check if user can edit (owner or admin/parent for shared/kids groups)
    can_edit_group = (
        group.owner == request.user or 
        current_member.role in ['ADMIN', 'PARENT']
    )
    
    # Children can only edit budget if it's a kids group and they're assigned
    can_edit_budget = can_edit_group
    if current_member.role == 'CHILD':
        can_edit_budget = False
    
    if request.method == 'POST' and can_edit_group:
        form = FlowGroupForm(request.POST, instance=group, family=family)
        if form.is_valid():
            flow_group = form.save(commit=False)
            
            # If Kids group is checked, automatically enable shared
            if flow_group.is_kids_group:
                flow_group.is_shared = True
            
            flow_group.save()
            
            # Save assigned children (ManyToMany field)
            form.save_m2m()
            
            messages.success(request, f"Flow Group '{group.name}' updated.")
            # Preserve period in redirect
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/flow-group/{group_id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm(instance=group, family=family)

    transactions = Transaction.objects.filter(flow_group=group).select_related('member__user').order_by('order', '-date')
    
    total_est = transactions.filter(date__range=(start_date, end_date)).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # AJUSTE DJANGO-MONEY
    if hasattr(total_est, 'amount'):
        total_estimated = Decimal(str(total_est.amount))
    else:
        total_estimated = total_est
    
    # AJUSTE DJANGO-MONEY: Extrair budgeted_amount
    budg_amt = group.budgeted_amount
    if hasattr(budg_amt, 'amount'):
        budg_amt_val = Decimal(str(budg_amt.amount))
    else:
        budg_amt_val = Decimal(str(budg_amt))
    
    budget_warning = total_estimated > budg_amt_val if budg_amt_val else False

    # Get default date for this period
    default_date = get_default_date_for_period(start_date, end_date)

    context = {
        'form': form,
        'is_new': False,
        'flow_group': group,
        'transactions': transactions,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'total_estimated': total_estimated,
        'budget_warning': budget_warning,
        'start_date': start_date,
        'end_date': end_date,
        'can_edit_group': can_edit_group,
        'can_edit_budget': can_edit_budget,
        'member_role_for_period' : member_role_for_period,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def members_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)

    context = {
        'family_members': family_members,
        'add_member_form': NewUserAndMemberForm(),
        'is_admin': current_member.role == 'ADMIN',
        'start_date': start_date,
        'end_date': end_date,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/members.html', context)


@login_required
@require_POST
@db_transaction.atomic
def add_member_view(request):
    """Handles adding a new family member."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        messages.error(request, 'User is not associated with a family.')
        return redirect('members')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can add new members.')
        return redirect('members')
    
    form = NewUserAndMemberForm(request.POST)
    
    # Preserve period in redirect
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    
    if form.is_valid():
        try:
            UserModel = get_user_model()
            new_user = UserModel.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email', ''),
                password=form.cleaned_data['password']
            )
            
            FamilyMember.objects.create(
                user=new_user,
                family=family,
                role=form.cleaned_data['role']
            )
            
            messages.success(request, f"Member '{new_user.username}' added successfully!")
            return redirect(f"/members/{redirect_url}")
            
        except Exception as e:
            messages.error(request, f"Error creating member: {str(e)}")
            return redirect(f"/members/{redirect_url}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect(f"/members/{redirect_url}")


@login_required
def edit_member_view(request, member_id):
    """Edit member details."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can edit members.')
        return redirect('members')
    
    member = get_object_or_404(FamilyMember, id=member_id, family=family)
    
    # Preserve period in redirect
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_info':
            username = request.POST.get('username')
            email = request.POST.get('email', '')
            role = request.POST.get('role')
            
            if username:
                UserModel = get_user_model()
                if UserModel.objects.filter(username=username).exclude(id=member.user.id).exists():
                    messages.error(request, 'Username already taken.')
                else:
                    member.user.username = username
                    member.user.email = email
                    member.user.save()
                    member.role = role
                    member.save()
                    messages.success(request, 'Member information updated successfully.')
            
        elif action == 'change_password':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if new_password and new_password == confirm_password:
                member.user.set_password(new_password)
                member.user.save()
                messages.success(request, 'Password changed successfully.')
            else:
                messages.error(request, 'Passwords do not match.')
        
        return redirect(f"/members/{redirect_url}")
    
    return redirect(f"/members/{redirect_url}")


@login_required
@require_POST
def remove_member_view(request, member_id):
    """Removes a member from the family."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        messages.error(request, 'User is not associated with a family.')
        return redirect('members')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can remove members.')
        return redirect('members')
    
    member_to_remove = get_object_or_404(FamilyMember, id=member_id, family=family)
    
    if member_to_remove.user == request.user:
        messages.error(request, 'You cannot remove yourself from the family.')
        return redirect('members')
    
    username = member_to_remove.user.username
    member_to_remove.delete()
    
    messages.success(request, f'Member {username} has been removed from the family.')
    
    # Preserve period in redirect
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/members/{redirect_url}")


@login_required
def investments_view(request):
    family, _, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    
    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            investment = form.save(commit=False)
            investment.family = family
            investment.save()
            messages.success(request, 'Investment added.')
            # Preserve period in redirect
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/investments/{redirect_url}")
    else:
        form = InvestmentForm()

    investments = Investment.objects.filter(family=family).order_by('name')
    
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    context = {
        'investment_form': form,
        'family_investments': investments,
        'start_date': start_date,
        'end_date': end_date,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/invest.html', context)


@login_required
def add_receipt_view(request):
    family, _, _ = get_family_context(request.user)
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)
    income_group = get_default_income_flow_group(family, request.user, start_date)
    # Preserve period in redirect
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/flow-group/{income_group.id}/edit/{redirect_url}")

# === AJAX endpoint for periods (optional, for dynamic loading) ===
@login_required
def get_periods_ajax(request):
    """
    Returns available periods as JSON for AJAX requests.
    """
    family, _, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    periods = get_available_periods(family)
    
    # Convert to JSON-serializable format
    periods_data = [{
        'label': p['label'],
        'value': p['value'],
        'is_current': p['is_current'],
        'has_data': p['has_data']
    } for p in periods]
    
    return JsonResponse({'periods': periods_data})

@login_required
@require_POST
@db_transaction.atomic
def copy_previous_period_ajax(request):
    """
    Copies all data from previous period to current period.
    Excludes child-created data.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    # Only admins and parents can copy period data
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Admins and Parents can copy period data.")
    
    try:
        # Check if current period already has data
        if current_period_has_data(family):
            return JsonResponse({
                'error': 'Current period already has data. Cannot copy.'
            }, status=400)
        
        # Copy data
        result = copy_previous_period_data(family, exclude_child_data=True)
        
        return JsonResponse({
            'status': 'success',
            'groups_copied': result['groups_copied'],
            'transactions_copied': result['transactions_copied'],
            'message': f"Copied {result['groups_copied']} groups and {result['transactions_copied']} transactions from previous period."
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error copying period: {str(e)}'}, status=500)


@login_required
def check_period_empty_ajax(request):
    """
    Checks if current period is empty (for showing copy button).
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        has_data = current_period_has_data(family)
        
        return JsonResponse({
            'status': 'success',
            'has_data': has_data,
            'can_copy': not has_data and current_member.role in ['ADMIN', 'PARENT']
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error checking period: {str(e)}'}, status=500)

@login_required
@require_POST
def save_bank_balance_ajax(request):
    """
    AJAX endpoint to save bank balance entries.
    """
    try:
        data = json.loads(request.body)
        
        family, current_member, _ = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': 'User not in family'}, status=403)
        
        description = data.get('description', '').strip()
        amount = Decimal(data.get('amount', '0'))
        date_str = data.get('date')
        member_id = data.get('member_id')
        period_start_date_str = data.get('period_start_date')
        balance_id = data.get('id')
        
        # Parse dates
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()
        period_start_date = dt_datetime.strptime(period_start_date_str, '%Y-%m-%d').date()
        
        # Get member if specified
        member = None
        if member_id and member_id != 'null':
            member = FamilyMember.objects.get(id=member_id, family=family)
        
        # AJUSTE DJANGO-MONEY: Criar Money object
        currency = family.configuration.base_currency
        money_amount = Money(amount, currency)
        
        # Create or update
        if balance_id and balance_id != 'new':
            # Update existing
            bank_balance = BankBalance.objects.get(id=balance_id, family=family)
            bank_balance.description = description
            bank_balance.amount = money_amount
            bank_balance.date = date
            bank_balance.member = member
            bank_balance.save()
        else:
            # Create new
            bank_balance = BankBalance.objects.create(
                family=family,
                member=member,
                description=description,
                amount=money_amount,
                date=date,
                period_start_date=period_start_date
            )
        
        # AJUSTE DJANGO-MONEY: Retornar valor numérico
        amount_value = str(bank_balance.amount.amount) if hasattr(bank_balance.amount, 'amount') else str(bank_balance.amount)
        
        return JsonResponse({
            'status': 'success',
            'id': bank_balance.id,
            'description': bank_balance.description,
            'amount': amount_value,
            'date': bank_balance.date.strftime('%Y-%m-%d'),
            'member_id': bank_balance.member.id if bank_balance.member else None,
            'member_name': bank_balance.member.user.username if bank_balance.member else 'Family',
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
@require_POST
def delete_bank_balance_ajax(request):
    """
    AJAX endpoint to delete bank balance entry.
    """
    try:
        data = json.loads(request.body)
        balance_id = data.get('id')
        
        family, _, _ = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': 'User not in family'}, status=403)
        
        bank_balance = BankBalance.objects.get(id=balance_id, family=family)
        bank_balance.delete()
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)





@login_required
@require_POST 
def investment_add_view(request):
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/investments/{redirect_url}")
