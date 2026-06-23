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

from django.apps import apps
for model in apps.get_models():
    count = model.objects.count()
    if count > 0:
        print(f"{model.__name__}: {count} rows")
