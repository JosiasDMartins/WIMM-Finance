import io
import tempfile
import json
import traceback
import importlib.util
import logging
from pathlib import Path
import sqlite3

from django.core.management import call_command
from django.http import JsonResponse, FileResponse
from django.utils.translation import gettext as _
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
    # Check if user is admin
    from ..models import FamilyMember
    is_admin = False
    if request.user.is_authenticated:
        member = FamilyMember.objects.filter(user=request.user).first()
        is_admin = member and member.role == 'ADMIN'

    target_version = VERSION

    print(f"[CHECK_UPDATES] DB: {get_db_version()}, Code: {target_version}, User: {request.user.username}, Is Admin: {is_admin}")

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
            'can_skip': False,
            'is_admin': is_admin
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
                'target_version': target_version,
                'is_admin': is_admin
            })

        container_required = requires_container_update(target_version, github_version)

        return JsonResponse({
            'needs_update': True,
            'update_type': 'github',
            'current_version': target_version,
            'target_version': github_version,
            'github_release': github_release,
            'requires_container': container_required,
            'can_skip': True,
            'is_admin': is_admin
        })

    print(f"[CHECK_UPDATES] No updates needed")
    return JsonResponse({
        'needs_update': False,
        'current_version': target_version,
        'target_version': target_version,
        'is_admin': is_admin
    })


@require_http_methods(["GET"])
def manual_check_updates(request):
    """Manually check for updates on the settings page."""
    # Check if user is admin
    from ..models import FamilyMember
    is_admin = False
    if request.user.is_authenticated:
        member = FamilyMember.objects.filter(user=request.user).first()
        is_admin = member and member.role == 'ADMIN'

    target_version = VERSION

    print(f"[MANUAL_CHECK] DB: {get_db_version()}, Code: {target_version}, User: {request.user.username}, Is Admin: {is_admin}")

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
            'can_skip': False,
            'is_admin': is_admin
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
            'can_skip': True,
            'is_admin': is_admin
        })

    # Nenhuma atualização disponível
    return JsonResponse({
        'needs_update': False,
        'current_version': target_version,
        'target_version': target_version,
        'is_admin': is_admin
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
    """
    Baixa e instala a atualização do GitHub.

    SECURITY: The backend determines which version to download based on the latest
    GitHub release, NOT from frontend input. This prevents malicious version injection.
    """
    try:
        print(f"[DOWNLOAD_GITHUB_UPDATE] Request received")
        print(f"[DOWNLOAD_GITHUB_UPDATE] Content-Type: {request.content_type}")
        print(f"[DOWNLOAD_GITHUB_UPDATE] Request body: {request.body[:500]}")

        data = json.loads(request.body)
        print(f"[DOWNLOAD_GITHUB_UPDATE] Parsed data: {data}")

        zipball_url = data.get('zipball_url')
        print(f"[DOWNLOAD_GITHUB_UPDATE] zipball_url from request: {zipball_url}")

        if not zipball_url:
            error_msg = f'Missing required parameter: zipball_url'
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] {error_msg}")
            return JsonResponse({
                'success': False,
                'error': _('Missing required parameter: zipball_url'),
                'details': error_msg
            }, status=400)

        # SECURITY: Determine target version from GitHub, not from frontend
        # Check the latest release to get the correct version
        print(f"[DOWNLOAD_GITHUB_UPDATE] Fetching latest release from GitHub to verify version...")
        has_github_update, github_release = check_github_update(VERSION)

        if not has_github_update or not github_release:
            error_msg = "Could not verify GitHub release information"
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] {error_msg}")
            return JsonResponse({
                'success': False,
                'error': _('Could not verify GitHub release information')
            }, status=400)

        # Extract version from the verified GitHub release
        target_version = github_release.get('version')
        expected_zipball_url = github_release.get('zipball_url')

        print(f"[DOWNLOAD_GITHUB_UPDATE] Verified target_version from GitHub: {target_version}")
        print(f"[DOWNLOAD_GITHUB_UPDATE] Expected zipball_url: {expected_zipball_url}")

        # SECURITY: Verify that the requested URL matches the official GitHub release URL
        if zipball_url != expected_zipball_url:
            error_msg = f"Security: Requested URL does not match official GitHub release URL"
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] {error_msg}")
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] Requested: {zipball_url}")
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] Expected: {expected_zipball_url}")
            return JsonResponse({
                'success': False,
                'error': _('Invalid download URL'),
                'details': error_msg
            }, status=403)

        if not target_version:
            error_msg = f'Could not determine target version from GitHub'
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] {error_msg}")
            return JsonResponse({
                'success': False,
                'error': _('Could not determine target version from GitHub')
            }, status=400)

        print(f"[DOWNLOAD_GITHUB_UPDATE] Starting download and extraction...")
        success, message, update_logs = download_and_extract_release(zipball_url)
        print(f"[DOWNLOAD_GITHUB_UPDATE] Download result: success={success}, message={message}")
        print(f"[DOWNLOAD_GITHUB_UPDATE] Logs captured: {len(update_logs)} lines")

        # Format logs for frontend
        logs_text = "\n".join(update_logs) if update_logs else "No detailed logs available"

        if not success:
            print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] Download failed: {message}")
            return JsonResponse({
                'success': False,
                'error': message,
                'filename': 'GitHub Update',
                'logs': logs_text
            })

        print(f"[DOWNLOAD_GITHUB_UPDATE] Setting version to {target_version}")
        SystemVersion.set_version(target_version)

        # Run migrations in development environment
        # In production (Docker), create flag for update_monitor to run migrations
        from ..docker_utils import is_running_in_docker

        if is_running_in_docker():
            print(f"[DOWNLOAD_GITHUB_UPDATE] Running in Docker - creating flags")
            create_migrate_flag()  # Create migrate flag
            create_reload_flag()   # Create reload flag
            reload_msg = "Docker flags created. Container will apply migrations and reload automatically."
        else:
            print(f"[DOWNLOAD_GITHUB_UPDATE] Running in development - applying migrations now")
            try:
                migration_success, migration_output = run_migrations()
                if migration_success:
                    reload_msg = "Migrations applied successfully. Please restart the development server."
                    print(f"[DOWNLOAD_GITHUB_UPDATE] Migrations applied: {migration_output}")
                else:
                    reload_msg = f"Warning: Migrations failed: {migration_output}"
                    print(f"[DOWNLOAD_GITHUB_UPDATE] Migration error: {migration_output}")
            except Exception as e:
                reload_msg = f"Warning: Migrations failed: {str(e)}"
                print(f"[DOWNLOAD_GITHUB_UPDATE] Migration exception: {e}")

        print(f"[DOWNLOAD_GITHUB_UPDATE] Update completed successfully")
        return JsonResponse({
            'success': True,
            'message': f"{message}\n{reload_msg}",
            'new_version': target_version,
            'needs_reload': True,
            'filename': 'GitHub Update',
            'logs': logs_text
        })

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in request body: {str(e)}"
        print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] {error_msg}")
        print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] Request body was: {request.body[:500]}")
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'traceback': traceback.format_exc()
        }, status=400)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        error_trace = traceback.format_exc()
        print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] {error_msg}")
        print(f"[DOWNLOAD_GITHUB_UPDATE ERROR] Traceback:\n{error_trace}")
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'traceback': error_trace
        }, status=500)


@require_http_methods(["POST"])
def create_backup(request):
    """Create a backup of the database.

    Automatically detects database backend (SQLite or PostgreSQL)
    and uses the appropriate backup strategy.
    """
    # Block backups in demo mode
    from django.conf import settings
    if getattr(settings, 'DEMO_MODE', False):
        return JsonResponse({'success': False, 'error': _('Database backups are disabled in demo mode.')}, status=403)

    try:
        # Use centralized backup function that handles both SQLite and PostgreSQL
        from finances.utils.db_backup import create_database_backup as create_db_backup

        result = create_db_backup()

        if result['success']:
            backup_path = Path(result['backup_path'])
            filename = result['filename']

            return JsonResponse({
                'success': True,
                'message': _('Backup created successfully'),
                'filename': filename,
                'download_url': f'/download-backup/{filename}/',
                'size': result.get('size', 0)
            })
        else:
            error_msg = result.get('error', 'Unknown error creating backup')
            return JsonResponse({'success': False, 'error': error_msg}, status=500)

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Backup error: {error_detail}")
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def download_backup(request, filename):
    """Provides a downloadable backup file."""
    # Block backup downloads in demo mode
    from django.conf import settings
    if getattr(settings, 'DEMO_MODE', False):
        return JsonResponse({'error': _('Backup downloads are disabled in demo mode.')}, status=403)

    try:
        # Try both possible backup locations
        # Location 1: db/backups (PostgreSQL backups and SQLite backups)
        backup_path = Path(settings.BASE_DIR) / 'db' / 'backups' / filename

        # Location 2: Old location for backwards compatibility
        if not backup_path.exists():
            backup_path = Path(settings.BASE_DIR) / 'backups' / filename

        if not backup_path.exists():
            logger.error(f"[DOWNLOAD_BACKUP] File not found: {filename}")
            logger.error(f"[DOWNLOAD_BACKUP] Tried paths:")
            logger.error(f"  - {Path(settings.BASE_DIR) / 'db' / 'backups' / filename}")
            logger.error(f"  - {Path(settings.BASE_DIR) / 'backups' / filename}")
            return JsonResponse({'error': _('Backup file not found')}, status=404)

        # Security check: ensure file is within allowed backup directories
        allowed_dirs = [
            str(Path(settings.BASE_DIR) / 'db' / 'backups'),
            str(Path(settings.BASE_DIR) / 'backups')
        ]

        resolved_path = str(backup_path.resolve())
        if not any(resolved_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
            logger.error(f"[DOWNLOAD_BACKUP] Security violation: {resolved_path} not in allowed dirs")
            return JsonResponse({'error': _('Invalid file path')}, status=403)

        logger.info(f"[DOWNLOAD_BACKUP] Serving file: {backup_path}")

        response = FileResponse(open(backup_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"[DOWNLOAD_BACKUP] Error: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def restore_backup(request):
    """Restores the database from a backup file.

    Supports all restore scenarios:
    - SQLite → SQLite (transactional restore)
    - SQLite → PostgreSQL (migration with confirmation)
    - PostgreSQL → PostgreSQL (transactional restore with backup)
    - PostgreSQL → SQLite (blocked with error message)
    """
    # Block database restore in demo mode
    from django.conf import settings
    if getattr(settings, 'DEMO_MODE', False):
        return JsonResponse({'success': False, 'error': _('Database restore is disabled in demo mode.')}, status=403)

    # Validate file upload
    if 'backup_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': _('No backup file provided')}, status=400)

    backup_file = request.FILES['backup_file']

    # STEP 1: Detect current database engine
    db_engine = settings.DATABASES['default']['ENGINE']

    if 'sqlite3' in db_engine:
        current_db_type = 'sqlite'
    elif 'postgresql' in db_engine:
        current_db_type = 'postgresql'
    else:
        return JsonResponse({
            'success': False,
            'error': _('Unsupported database engine: %(engine)s') % {'engine': db_engine}
        }, status=400)

    logger.info(f"[RESTORE_BACKUP] Current database type: {current_db_type}")

    # STEP 2: Save uploaded file to temporary location to detect type
    import tempfile
    from pathlib import Path

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.backup')
    temp_path = Path(temp_file.name)
    temp_file.close()

    try:
        with open(temp_path, 'wb') as f:
            for chunk in backup_file.chunks():
                f.write(chunk)

        logger.info(f"[RESTORE_BACKUP] Backup file saved to temp: {temp_path}")

        # STEP 3: Detect backup file type
        from finances.utils.db_type_detector import detect_backup_type
        backup_file_type = detect_backup_type(temp_path)

        logger.info(f"[RESTORE_BACKUP] Backup file type: {backup_file_type}")

        if backup_file_type == 'unknown':
            return JsonResponse({
                'success': False,
                'error': _('Could not determine backup file type. Please ensure this is a valid SQLite or PostgreSQL backup file.')
            }, status=400)

        # STEP 4: Check if migration is needed and if confirmation was provided
        migration_needed = (backup_file_type == 'sqlite' and current_db_type == 'postgresql')
        migration_confirmed = request.POST.get('confirm_migration') == 'true'

        logger.info(f"[RESTORE_BACKUP] Migration needed: {migration_needed}, Confirmed: {migration_confirmed}")

        # STEP 5: Handle different restore scenarios

        # SCENARIO 1: PostgreSQL → SQLite (BLOCKED)
        if backup_file_type == 'postgresql' and current_db_type == 'sqlite':
            logger.error(f"[RESTORE_BACKUP] Attempted to restore PostgreSQL backup to SQLite system")
            return JsonResponse({
                'success': False,
                'error': _('Cannot restore PostgreSQL backup to SQLite database'),
                'details': _('Your system is currently running with SQLite database, but you are trying to restore a PostgreSQL backup. This operation is not supported. Please restore a SQLite backup file instead.')
            }, status=400)

        # SCENARIO 2: SQLite → PostgreSQL (MIGRATION - needs confirmation)
        elif backup_file_type == 'sqlite' and current_db_type == 'postgresql':
            if not migration_confirmed:
                # Return special response asking for confirmation
                logger.info(f"[RESTORE_BACKUP] Migration required, asking for confirmation")
                return JsonResponse({
                    'success': False,
                    'needs_migration_confirmation': True,
                    'backup_type': 'sqlite',
                    'current_db_type': 'postgresql',
                    'error': _('Migration Required'),
                    'message': _('The backup file is from SQLite, but your system is running PostgreSQL. The data will be migrated from SQLite to PostgreSQL. This operation will drop all current data in PostgreSQL. Do you want to proceed?')
                }, status=200)  # Not an error, just asking for confirmation
            else:
                # Confirmation received, proceed with migration
                logger.info(f"[RESTORE_BACKUP] Migration confirmed, proceeding")

                # Reopen file for migration function
                with open(temp_path, 'rb') as f:
                    from django.core.files.uploadedfile import InMemoryUploadedFile
                    from io import BytesIO

                    file_content = f.read()
                    backup_file_for_migration = InMemoryUploadedFile(
                        BytesIO(file_content),
                        'backup_file',
                        'backup.sqlite3',
                        'application/octet-stream',
                        len(file_content),
                        None
                    )

                from finances.utils.db_restore_migration import restore_sqlite_to_postgres
                result = restore_sqlite_to_postgres(backup_file_for_migration)

        # SCENARIO 3: SQLite → SQLite (TRANSACTIONAL RESTORE)
        elif backup_file_type == 'sqlite' and current_db_type == 'sqlite':
            logger.info(f"[RESTORE_BACKUP] SQLite to SQLite restore")

            # Reopen file for restore function
            with open(temp_path, 'rb') as f:
                from django.core.files.uploadedfile import InMemoryUploadedFile
                from io import BytesIO

                file_content = f.read()
                backup_file_for_restore = InMemoryUploadedFile(
                    BytesIO(file_content),
                    'backup_file',
                    'backup.sqlite3',
                    'application/octet-stream',
                    len(file_content),
                    None
                )

            from finances.utils.db_restore import restore_database_from_file
            result = restore_database_from_file(backup_file_for_restore)

        # SCENARIO 4: PostgreSQL → PostgreSQL (TRANSACTIONAL RESTORE)
        elif backup_file_type == 'postgresql' and current_db_type == 'postgresql':
            logger.info(f"[RESTORE_BACKUP] PostgreSQL to PostgreSQL restore")

            # Reopen file for restore function
            with open(temp_path, 'rb') as f:
                from django.core.files.uploadedfile import InMemoryUploadedFile
                from io import BytesIO

                file_content = f.read()
                backup_file_for_restore = InMemoryUploadedFile(
                    BytesIO(file_content),
                    'backup_file',
                    'backup.dump',
                    'application/octet-stream',
                    len(file_content),
                    None
                )

            from finances.utils.db_restore_postgres import restore_postgres_database_from_file
            result = restore_postgres_database_from_file(backup_file_for_restore)

        else:
            # Should never reach here
            logger.error(f"[RESTORE_BACKUP] Unexpected scenario: {backup_file_type} → {current_db_type}")
            return JsonResponse({
                'success': False,
                'error': _('Unexpected restore scenario')
            }, status=500)

    finally:
        # Clean up temporary file
        try:
            if temp_path.exists():
                temp_path.unlink()
                logger.info(f"[RESTORE_BACKUP] Temporary file deleted")
        except Exception as e:
            logger.warning(f"[RESTORE_BACKUP] Could not delete temp file: {e}")

    # Handle result
    if not result['success']:
        return JsonResponse(result, status=400 if 'corrupted' in result.get('error', '') else 500)

    # Create JSON response
    response = JsonResponse(result)

    # CRITICAL: Delete the session cookie to prevent loops
    # The old session from the previous DB no longer exists in the restored DB
    session_cookie_name = settings.SESSION_COOKIE_NAME
    response.delete_cookie(
        session_cookie_name,
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
    )

    return response



@require_http_methods(["POST"])
def skip_updates(request):
    """Skip GitHub updates by marking the version as skipped in the database."""
    try:
        data = json.loads(request.body)
        update_type = data.get('update_type', 'local')
        version = data.get('version')

        if update_type == 'local':
            return JsonResponse({'success': False, 'error': _('Local updates cannot be skipped')}, status=400)

        if not version:
            return JsonResponse({'success': False, 'error': _('Version is required')}, status=400)

        # Mark this version as skipped
        SkippedUpdate.skip_version(version)
        print(f"[SKIP_UPDATES] Version {version} marked as skipped")

        return JsonResponse({
            'success': True,
            'skipped_version': version,
            'message': _('Version %(version)s will not be shown again until a newer version is available') % {'version': version}
        })

    except Exception as e:
        print(f"[SKIP_UPDATES] Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)