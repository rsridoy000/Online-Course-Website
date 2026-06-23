import os
import django
import sys

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')
django.setup()

from django.conf import settings
from quiz_app.models import Quiz, StudentAttempt

def cleanup_duplicates():
    # Print the database configuration name
    db_engine = settings.DATABASES['default']['ENGINE']
    db_name = settings.DATABASES['default'].get('NAME', '')
    db_host = settings.DATABASES['default'].get('HOST', '')
    print(f"Connecting to database engine: {db_engine}")
    if 'sqlite' in db_engine:
        print(f"Database File: {db_name}")
    else:
        print(f"Database Host: {db_host}")

    # Get all distinct student names who have attempts
    student_names = StudentAttempt.objects.values_list('student_name', flat=True).distinct()
    
    total_deleted = 0
    
    for s_name in student_names:
        if not s_name:
            continue
            
        # Get all quizzes attempted by this student
        quizzes = StudentAttempt.objects.filter(student_name=s_name).values_list('quiz', flat=True).distinct()
        
        for quiz_id in quizzes:
            # Find all unsubmitted (In Progress) attempts for this student and quiz
            attempts = list(StudentAttempt.objects.filter(
                student_name=s_name, 
                quiz_id=quiz_id, 
                is_submitted=False
            ).order_by('-started_at'))
            
            if len(attempts) > 1:
                print(f"\nFound {len(attempts)} In-Progress attempts for student '{s_name}' on quiz ID {quiz_id}")
                
                # Sort attempts by how many answers they have (most answers first), then by latest started_at
                attempts.sort(key=lambda a: (a.answers.count(), a.started_at), reverse=True)
                
                # Keep the best one (index 0)
                keep_attempt = attempts[0]
                delete_attempts = attempts[1:]
                
                print(f"Keeping attempt: ID {keep_attempt.id} started at {keep_attempt.started_at} (Answers count: {keep_attempt.answers.count()})")
                
                for da in delete_attempts:
                    print(f"Deleting duplicate attempt: ID {da.id} started at {da.started_at} (Answers count: {da.answers.count()})")
                    da.delete()
                    total_deleted += 1
                    
    print(f"\nCleanup complete. Total duplicate attempts deleted: {total_deleted}")

if __name__ == "__main__":
    cleanup_duplicates()
