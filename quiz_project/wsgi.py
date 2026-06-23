"""
WSGI config for quiz_project project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')

application = get_wsgi_application()
app = application
