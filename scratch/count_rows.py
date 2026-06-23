import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')
django.setup()

from django.apps import apps

for model in apps.get_models():
    count = model.objects.count()
    if count > 0:
        print(f"{model.__name__}: {count} rows")
