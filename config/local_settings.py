
import os

DEBUG = False
CSRF_TRUSTED_ORIGINS = ['you_domain']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
