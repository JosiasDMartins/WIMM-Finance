"""
Views package initializer.

This __init__.py file imports all functions from their respective modules
so that the main 'views.py' file (in the app root) can import them
using 'from .views import *'.
"""

from .views_utils import *
from .views_auth import *
from .views_updater import *
from .views_pages import *
from .views_ajax import *