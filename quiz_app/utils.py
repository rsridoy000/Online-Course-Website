import os
from django.conf import settings
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from django.core.files.base import ContentFile
from .models import StudentAttempt, AssignmentSubmission, SessionReport, Quiz, Assignment

def generate_submission_report(activity_type, activity_id):
    """
    Generates a PDF report for a Quiz or Assignment.
    Only includes students who submitted/completed the activity.
    """
    data = []
    activity_name = ""
    
    if activity_type == 'quiz':
        quiz = Quiz.objects.get(id=activity_id)
        activity_name = quiz.title
        # Fetch only submitted attempts
        attempts = StudentAttempt.objects.filter(
            quiz=quiz, is_submitted=True
        ).select_related('student', 'student__student_profile').order_by('-score', 'submitted_at')
        
        for idx, att in enumerate(attempts, 1):
            profile = getattr(att.student, 'student_profile', None)
            student_id = profile.student_id if profile else "N/A"
            data.append({
                'serial': idx,
                'name': att.student_name,
                'student_id': student_id,
                'marks': f"{att.score}/{att.total_questions}",
                'raw_score': att.score
            })
            
    elif activity_type == 'assignment':
        assignment = Assignment.objects.get(id=activity_id)
        activity_name = assignment.title
        # Fetch only submitted and graded assignments
        submissions = AssignmentSubmission.objects.filter(
            assignment=assignment
        ).select_related('student', 'student__student_profile').order_by('-marks', 'submitted_at')
        
        for idx, sub in enumerate(submissions, 1):
            profile = getattr(sub.student, 'student_profile', None)
            student_id = profile.student_id if profile else "N/A"
            name = sub.student.get_full_name() or sub.student.username
            data.append({
                'serial': idx,
                'name': name,
                'student_id': student_id,
                'marks': f"{sub.marks}/{assignment.total_marks}",
                'raw_score': sub.marks
            })

    if not data:
        return None # No submissions to report

    from django.utils import timezone

    context = {
        'activity_name': activity_name,
        'activity_type': activity_type.capitalize(),
        'data': data,
        'generated_at': timezone.now()
    }
    
    # Render HTML template
    template = get_template('reports/pdf_template.html')
    html = template.render(context)
    
    # Create PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        filename = f"{activity_type}_report_{activity_id}.pdf"
        report_file = ContentFile(result.getvalue(), name=filename)
        
        # Save to model
        report_obj, created = SessionReport.objects.update_or_create(
            report_type=activity_type,
            quiz_id=activity_id if activity_type == 'quiz' else None,
            assignment_id=activity_id if activity_type == 'assignment' else None,
            defaults={'report_file': report_file}
        )
        return report_obj
    
    return None
