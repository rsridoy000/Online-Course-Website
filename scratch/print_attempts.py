import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')
django.setup()

from quiz_app.models import StudentAttempt

attempts = StudentAttempt.objects.all().order_by('-started_at')[:20]
for a in attempts:
    print(f"ID: {a.id}, Student: {a.student_name}, Quiz: {a.quiz.title}, Submitted: {a.is_submitted}, Started: {a.started_at}, Score: {a.score}, TotalQ: {a.total_questions}")
