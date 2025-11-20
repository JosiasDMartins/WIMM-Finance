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

from ..models import SystemVersion, SkippedUpdate
from ..version_utils import Version, needs_update
from ..github_utils import (
    check_github_update, 
    requires_container_update,
    download_and_extract_release,
    create_database_backup
)

from ..version_utils import SKIP_LOCAL_UPDATE, FORCE_UPDATE_FOR_TESTING

from ..context_processors import VERSION
from ..docker_utils import create_reload_flag, create_requirements_flag, create_migrate_flag



def get_db_version():
    db_version = None
    try:
        db_version = SystemVersion.get_current_version()
    except (OperationalError, ProgrammingError):
        pass
        
    if db_version is None or db_version == '' or db_version.strip() == '':
        db_version = "0.0.0"
    
    return db_version

def check_for_updates(request):
    """
    Check for local and GitHub updates.
    Priority: Local > GitHub
    """

    

    target_version = VERSION
    
    print(f"[CHECK_UPDATES] DB: {get_db_version()}, Code: {target_version}")
    
    # Verifica atualizações locais primeiro
    local_update_needed = False
    if not SKIP_LOCAL_UPDATE:
        try:
            local_update_needed = needs_update(get_db_version(), target_version)
        except ValueError:
            local_update_needed = True
    
    if local_update_needed:
        local_scripts = get_available_update_scripts(get_db_version(), target_version)
        print(f"[CHECK_UPDATES] Local update needed. Scripts: {len(local_scripts)}")
        
        return JsonResponse({
            'needs_update': True,
            'update_type': 'local',
            'current_version': get_db_version(),
            'target_version': target_version,
            'has_scripts': len(local_scripts) > 0,
            'update_scripts': local_scripts,
            'can_skip': False
        })
    
    # No local updates, check GitHub
    has_github_update, github_release = check_github_update(target_version)

    if has_github_update:
        github_version = github_release['version']

        # Check if this version was already skipped
        if SkippedUpdate.is_version_skipped(github_version):
            print(f"[CHECK_UPDATES] Version {github_version} was skipped, not showing")
            return JsonResponse({
                'needs_update': False,
                'current_version': target_version,
                'target_version': target_version
            })

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
    
    print(f"[CHECK_UPDATES] No updates needed")
    return JsonResponse({
        'needs_update': False,
        'current_version': target_version,
        'target_version': target_version
    })


@require_http_methods(["GET"])
def manual_check_updates(request):
    """Manually check for updates on the settings page."""
    target_version = VERSION
    
    print(f"[MANUAL_CHECK] DB: {get_db_version()}, Code: {target_version}")
    
    local_update_needed = False
    if not SKIP_LOCAL_UPDATE:
        try:
            local_update_needed = needs_update(get_db_version(), target_version)
        except ValueError:
            local_update_needed = True
    
    # Se há update local, retorna dados completos para abrir o modal
    if local_update_needed:
        local_scripts = get_available_update_scripts(get_db_version(), target_version)
        
        return JsonResponse({
            'needs_update': True,
            'update_type': 'local',
            'current_version': get_db_version(),
            'target_version': target_version,
            'has_scripts': len(local_scripts) > 0,
            'update_scripts': local_scripts,
            'can_skip': False
        })
    
    # Check GitHub (manual check clears skipped versions)
    SkippedUpdate.clear_skipped_versions()
    has_github_update, github_release = check_github_update(target_version)

    # If there's a GitHub update, return full data to open modal
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
    
    # Nenhuma atualização disponível
    return JsonResponse({
        'needs_update': False,
        'current_version': target_version,
        'target_version': target_version
    })


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
        print(f"[APPLY_UPDATES] Starting...")
        print(f"[APPLY_UPDATES] Content-Type: {request.content_type}")
        print(f"[APPLY_UPDATES] Body: {request.body[:200]}")  # Primeiros 200 chars
        
        # Parse request body - pode estar vazio ou ter JSON
        scripts = []
        if request.body:
            try:
                data = json.loads(request.body)
                scripts = data.get('scripts', [])
            except json.JSONDecodeError as e:
                print(f"[APPLY_UPDATES] JSON decode error: {e}")
                # Continua mesmo sem scripts - irá pegar da DB
        
        # Se não veio scripts no body, busca do banco
        if not scripts:            
            scripts = get_available_update_scripts(get_db_version(), VERSION)
            print(f"[APPLY_UPDATES] Found {len(scripts)} scripts from DB version {get_db_version()}")
        
        results = []
        all_success = True
        
        # 1. Run migrations
        print(f"[APPLY_UPDATES] Running migrations...")
        migration_success, migration_output = run_migrations()
        
        results.append({
            'type': 'migration',
            'status': 'success' if migration_success else 'error',
            'output': migration_output
        })
        
        if not migration_success:
            all_success = False
            return JsonResponse({
                'success': False,
                'results': results,
                'error': 'Migration failed'
            })
        
        # 2. Execute update scripts
        if scripts:
            print(f"[APPLY_UPDATES] Executing {len(scripts)} scripts...")
            for script in scripts:
                script_path = script.get('path') or script.get('filename')
                script_version = script.get('version', 'unknown')
                
                result = {
                    'type': 'script',
                    'filename': Path(script_path).name,
                    'version': script_version,
                    'status': 'pending'
                }
                
                try:
                    output = execute_update_script(script_path)
                    result['status'] = 'success'
                    result['output'] = output
                    print(f"[APPLY_UPDATES] Script success: {output}")
                except Exception as e:
                    result['status'] = 'error'
                    result['error'] = str(e)
                    result['traceback'] = traceback.format_exc()
                    all_success = False
                    print(f"[APPLY_UPDATES] Script failed: {e}")
                    results.append(result)
                    break
                
                results.append(result)
        
        # 3. Update version in DB if all successful
        if all_success:
            SystemVersion.set_version(VERSION)
            print(f"[APPLY_UPDATES] Version updated to {VERSION}")

            # 4. Create reload flag for Docker hot-reload
            if create_reload_flag():
                print(f"[APPLY_UPDATES] Reload flag created for Docker")

        response_data = {
            'success': all_success,
            'results': results,
            'new_version': VERSION if all_success else SystemVersion.get_current_version()
        }

        print(f"[APPLY_UPDATES] Finished. Success: {all_success}")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"[APPLY_UPDATES] Exception: {e}")
        print(f"[APPLY_UPDATES] Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


def execute_update_script(script_path):
    """Executes an update script and returns the output."""
    # Se script_path é só o nome do arquivo, construir o path completo
    if not Path(script_path).exists():
        scripts_dir = Path(settings.BASE_DIR) / 'update_scripts'
        script_path = scripts_dir / script_path
    
    print(f"[EXECUTE_SCRIPT] Loading from: {script_path}")
    
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

        # Create flags for Docker hot-reload
        # Check if requirements changed and create appropriate flags
        requirements_changed = False  # TODO: Implement requirements comparison
        if requirements_changed:
            create_requirements_flag()
        else:
            create_reload_flag()

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
        
        # Pega o caminho correto do banco de dados do Django settings
        db_path = Path(settings.DATABASES['default']['NAME'])
        
        temp_path = db_path.parent / 'temp_restore.sqlite3'
        
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
        
        # Backup do banco atual antes de substituir
        if db_path.exists():
            backup_old = db_path.parent / f'{db_path.name}.old'
            shutil.copy2(db_path, backup_old)
        
        # Move o arquivo temporário para o local correto
        shutil.move(str(temp_path), str(db_path))
        
        return JsonResponse({
            'success': True,
            'family': family_info,
            'users': users_info,
            'message': 'Database restored successfully'
        })
        
    except Exception as e:
        # Limpa arquivo temporário em caso de erro
        db_path = Path(settings.DATABASES['default']['NAME'])
        temp_path = db_path.parent / 'temp_restore.sqlite3'
        if temp_path.exists():
            temp_path.unlink()
        
        return JsonResponse({'success': False, 'error': f'Restore failed: {str(e)}'}, status=500)


@require_http_methods(["POST"])
def skip_updates(request):
    """Skip GitHub updates by marking the version as skipped in the database."""
    try:
        data = json.loads(request.body)
        update_type = data.get('update_type', 'local')
        version = data.get('version')

        if update_type == 'local':
            return JsonResponse({'success': False, 'error': 'Local updates cannot be skipped'}, status=400)

        if not version:
            return JsonResponse({'success': False, 'error': 'Version is required'}, status=400)

        # Mark this version as skipped
        SkippedUpdate.skip_version(version)
        print(f"[SKIP_UPDATES] Version {version} marked as skipped")

        return JsonResponse({
            'success': True,
            'skipped_version': version,
            'message': f'Version {version} will not be shown again until a newer version is available'
        })

    except Exception as e:
        print(f"[SKIP_UPDATES] Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)