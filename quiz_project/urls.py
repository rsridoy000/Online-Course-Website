"""
URL configuration for quiz_project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

handler400 = 'quiz_app.views.custom_bad_request_handler'


def security_txt(request):
    security_info = (
        "Contact: mailto:security@yourdomain.com\n"
        "Expires: 2027-12-31T23:59:59.000Z\n"
        "Preferred-Languages: en\n"
        "Canonical: https://liquidtripler.vercel.app/.well-known/security.txt\n"
    )
    return HttpResponse(security_info, content_type="text/plain")

urlpatterns = [
    path('.well-known/security.txt', security_txt),
    path('django-admin/', admin.site.urls),
    path('', include('quiz_app.urls')),
]


if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
