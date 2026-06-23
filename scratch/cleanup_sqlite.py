import os
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')

import django
from django.conf import settings

# Initialize django settings but override DATABASES to SQLite first
from django.conf import LazySettings
settings._setup()
settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3',
    }
}

django.setup()

from scratch.cleanup_duplicate_attempts import cleanup_duplicates

if __name__ == "__main__":
    cleanup_duplicates()
