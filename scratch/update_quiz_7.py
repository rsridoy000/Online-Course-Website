
import os
import django
import sys

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')
django.setup()

from quiz_app.models import Quiz, StudentAttempt, WarningLog

def update_quiz_7_penalties():
    # Attempt to find Quiz 7. If ID 7 doesn't exist, we'll look for a quiz with "7" in title.
    try:
        quiz = Quiz.objects.get(id=7)
        print(f"Found Quiz: {quiz.title} (ID: 7)")
    except Quiz.DoesNotExist:
        quiz = Quiz.objects.filter(title__icontains="7").first()
        if quiz:
            print(f"Found Quiz by title: {quiz.title} (ID: {quiz.id})")
        else:
            print("Quiz 7 not found by ID or Title.")
            return

    attempts = StudentAttempt.objects.filter(quiz=quiz)
    updated_count = 0

    for attempt in attempts:
        # Count actual warnings from WarningLog for this attempt
        warning_count = WarningLog.objects.filter(attempt=attempt).count()
        
        # Also sync with tab_switch_count if needed
        attempt.tab_switch_count = warning_count
        
        original_score = attempt.score
        
        if warning_count >= 2:
            attempt.score = 0
            attempt.is_disqualified = True
            print(f"Disqualified: {attempt.student_name} ({warning_count} switches) -> Score 0")
        elif warning_count == 1:
            # We need to recalculate from base if possible, but for simplicity we'll just deduct 2
            # Assuming score was already calculated.
            attempt.score = max(0, attempt.score - 2)
            print(f"Penalty: {attempt.student_name} (1 switch) -> Score {original_score} to {attempt.score}")
        
        attempt.save()
        updated_count += 1

    print(f"Successfully updated {updated_count} attempts for {quiz.title}.")

if __name__ == "__main__":
    update_quiz_7_penalties()
