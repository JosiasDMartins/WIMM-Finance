import io
import shutil
import json
import traceback
import importlib.util
from pathlib import Path
import sqlite3

from django.core.management import call_command
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.utils import OperationalError, ProgrammingError
from django.conf import settings

# Importações relativas do app (.. sobe um nível, de /views/ para /finances/)
from ..models import SystemVersion
from ..version_utils import Version, needs_update
from ..github_utils import (
    check_github_update, 
    requires_container_update,
    download_and_extract_release,
    create_database_backup
)
from .views_utils import VERSION


def check_for_updates(request):
    """
    Check for local and GitHub updates.
    Priority: Local > GitHub
    """
    target_version = VERSION
    
    db_version = None
    try:
        db_version = SystemVersion.get_current_version()
    except (OperationalError, ProgrammingError):
        pass
    
    if db_version is None or db_version == '' or db_version.strip() == '':
        db_version = "0.0.0"
    
    # Verifica atualizações locais primeiro
    local_update_needed = False
    try:
        local_update_needed = needs_update(db_version, target_version)
    except ValueError:
        local_update_needed = True
    
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
    
    # Sem atualizações locais, verifica GitHub
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
    """Manually check for updates on the settings page."""
    target_version = VERSION
    db_version = SystemVersion.get_current_version() or "0.0.0"
    
    local_update_needed = False
    try:
        local_update_needed = needs_update(db_version, target_version)
    except ValueError:
        local_update_needed = True
    
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
    """Find update scripts that need to be run."""
    scripts_dir = Path(settings.BASE_DIR) / 'update_scripts'
    
    if not scripts_dir.exists():
        return []
    
    try:
        from_ver = Version(from_version if from_version != "0.0.0" else "0.0.0")
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
    """Execute 'makemigrations' and 'migrate'."""
    try:
        output = io.StringIO()
        call_command('makemigrations', stdout=output, stderr=output, interactive=False)
        call_command('migrate', stdout=output, stderr=output, interactive=False)
        return True, output.getvalue()
    except Exception as e:
        return False, str(e)


@require_http_methods(["POST"])
def apply_local_updates(request):
    """Applies local updates: runs migrations and scripts."""
    try:
        data = json.loads(request.body)
        scripts = data.get('scripts', [])
        
        results = []
        all_success = True
        
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
    """Executes an update script and returns the output."""
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
    """Baixa e instala a atualização do GitHub."""
    try:
        data = json.loads(request.body)
        zipball_url = data.get('zipball_url')
        target_version = data.get('target_version')
        
        if not zipball_url or not target_version:
            return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)
        
        success, message = download_and_extract_release(zipball_url)
        
        if not success:
            return JsonResponse({'success': False, 'error': message})
        
        SystemVersion.set_version(target_version)
        
        return JsonResponse({
            'success': True,
            'message': message,
            'new_version': target_version,
            'needs_reload': True
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["POST"])
def create_backup(request):
    """Create a backup of the database."""
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
            return JsonResponse({'success': False, 'error': message}, status=500)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def download_backup(request, filename):
    """Provides a downloadable backup file."""
    try:
        backup_path = Path(settings.BASE_DIR) / 'backups' / filename
        
        if not backup_path.exists():
            return JsonResponse({'error': 'Backup file not found'}, status=404)
        
        if not str(backup_path.resolve()).startswith(str(Path(settings.BASE_DIR) / 'backups')):
            return JsonResponse({'error': 'Invalid file path'}, status=403)
        
        response = FileResponse(open(backup_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def restore_backup(request):
    """Restores the database from a backup file."""
    try:
        if 'backup_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No backup file provided'}, status=400)
        
        backup_file = request.FILES['backup_file']
        
        temp_path = Path(settings.BASE_DIR) / 'temp_restore.sqlite3'
        
        with open(temp_path, 'wb+') as destination:
            for chunk in backup_file.chunks():
                destination.write(chunk)
        
        conn = sqlite3.connect(str(temp_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM finances_family LIMIT 1")
        family_row = cursor.fetchone()
        
        family_info = None
        users_info = []
        
        if family_row:
            family_id, family_name = family_row
            family_info = {'id': family_id, 'name': family_name}
            
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
        temp_path = Path(settings.BASE_DIR) / 'temp_restore.sqlite3'
        if temp_path.exists():
            temp_path.unlink()
        
        return JsonResponse({'success': False, 'error': f'Restore failed: {str(e)}'}, status=500)


@require_http_methods(["POST"])
def skip_updates(request):
    """Skip GitHub updates by marking the current version.."""
    try:
        data = json.loads(request.body)
        update_type = data.get('update_type', 'local')
        
        if update_type == 'local':
            return JsonResponse({'success': False, 'error': 'Local updates cannot be skipped'}, status=400)
        
        target_version = VERSION
        SystemVersion.set_version(target_version)
        
        return JsonResponse({'success': True, 'new_version': target_version})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)