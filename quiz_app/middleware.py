from django.utils import timezone
from .models import StudentProfile

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Try to update last_activity for students
            try:
                # We use update() to avoid triggering the save() method and for better performance
                # But we only update if it's been more than 1 minute since last update to save DB writes
                profile = request.user.student_profile
                now = timezone.now()
                
                # Update last activity
                if not profile.last_activity or (now - profile.last_activity).total_seconds() > 60:
                    profile.last_activity = now
                    profile.save(update_fields=['last_activity'])

                # Update section view timestamps
                path = request.path
                updated_ts = False
                if '/quiz-list/' in path or '/quiz/' in path:
                    profile.view_timestamps['quizzes'] = now.isoformat()
                    updated_ts = True
                elif '/assignments/' in path:
                    profile.view_timestamps['assignments'] = now.isoformat()
                    updated_ts = True
                elif '/resources/' in path:
                    profile.view_timestamps['resources'] = now.isoformat()
                    updated_ts = True
                elif '/notices/' in path:
                    profile.view_timestamps['notices'] = now.isoformat()
                    updated_ts = True
                
                if updated_ts:
                    profile.save(update_fields=['view_timestamps'])
            except Exception:
                pass
        
        response = self.get_response(request)
        return response


class RemoveFingerprintingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Remove or mask fingerprinting/technical disclosure headers
        sensitive_headers = ['Server', 'X-Powered-By', 'X-Runtime']
        for header in sensitive_headers:
            if response.has_header(header):
                del response[header]
                
        return response


import traceback
from django.http import HttpResponse

class ExceptionLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as e:
            tb = traceback.format_exc()
            return HttpResponse(
                f"Diagnostic Exception:\n\n{str(e)}\n\nTraceback:\n{tb}",
                content_type="text/plain",
                status=500
            )


