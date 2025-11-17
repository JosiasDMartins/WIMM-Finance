from .models import SystemVersion

#Files version
VERSION = "1.0.0-alpha5"


#Legacy - This is the var name used at views_updater
db_version = None
try:
    db_version = SystemVersion.get_current_version()
except (OperationalError, ProgrammingError):
    pass
    
if db_version is None or db_version == '' or db_version.strip() == '':
    db_version = "0.0.0"
    
#General contect for the entire system
def database_version(request):
    
    try:
        return {'db_version': db_version or '0.0.0'}
    except:
        return {'db_version': '0.0.0'}

def app_version(request):
    return {'app_version': VERSION}
