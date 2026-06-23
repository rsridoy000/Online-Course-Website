from django.urls import path
from . import views

urlpatterns = [

    # ── Student Auth ──────────────────────────────────────────
    path('register/', views.student_register, name='student_register'),
    path('otp-verify/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('login/', views.student_login, name='student_login'),
    path('logout/', views.student_logout, name='student_logout'),
    path('profile/', views.student_profile, name='student_profile'),
    path('password-reset/', views.student_password_reset, name='student_password_reset'),
    path('password-reset/verify/', views.student_password_reset_verify, name='student_password_reset_verify'),
    path('password-reset/resend-otp/', views.resend_password_reset_otp, name='resend_password_reset_otp'),
    path('password-reset/confirm/', views.student_password_reset_confirm, name='student_password_reset_confirm'),


    # ── Admin Auth ────────────────────────────────────────────
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin/login/', views.admin_login),
    path('admin-logout/', views.admin_logout, name='admin_logout'),
    path('admin/logout/', views.admin_logout),

    # ── Admin Dashboard & Profile ─────────────────────────────
    path('admin/', views.admin_dashboard),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/', views.admin_dashboard),
    path('admin/cleanup-duplicates/', views.admin_cleanup_duplicates, name='admin_cleanup_duplicates'),
    path('admin/profile/', views.admin_profile, name='admin_profile'),
    path('admin-profile/', views.admin_profile),
    path('admin/profile/remove-image/', views.remove_admin_profile_image, name='remove_admin_profile_image'),
    path('profile/remove-image/', views.remove_profile_image, name='remove_profile_image'),
    path('admin-reports/', views.admin_reports, name='admin_reports'),
    path('admin/reports/', views.admin_reports),
    path('add-assignment/', views.add_assignment, name='add_assignment'),
    path('assignment/<int:assignment_id>/edit/', views.edit_assignment, name='edit_assignment'),
    path('assignment/<int:assignment_id>/delete/', views.delete_assignment, name='delete_assignment'),

    path('quiz/create/', views.create_quiz, name='create_quiz'),
    path('quiz/<int:quiz_id>/detail/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('quiz/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    path('quiz/<int:quiz_id>/toggle-publish/', views.toggle_quiz_publish, name='toggle_quiz_publish'),

    path('quiz/<int:quiz_id>/add-question/', views.add_question, name='add_question'),
    path('question/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('question/<int:question_id>/delete/', views.delete_question, name='delete_question'),

    path('attempt/<int:attempt_id>/view/', views.view_attempt, name='view_attempt'),
    path('attempt/<int:attempt_id>/delete/', views.delete_attempt, name='delete_attempt'),

    # ── Student Dashboard ─────────────────────────────────────
    path('', views.student_dashboard, name='home'),
    path('quiz-list/', views.home, name='quiz_list'),

    # ── Assignments ───────────────────────────────────────────
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/<int:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('admin/submissions/', views.admin_submissions, name='admin_submissions'),
    path('submission/<int:submission_id>/grade/', views.grade_submission, name='grade_submission'),
    path('submission/<int:submission_id>/publish/', views.publish_assignment_result, name='publish_result'),
    path('submission/<int:submission_id>/cancel-grade/', views.cancel_grade, name='cancel_grade'),
    path('admin/submissions/publish-all/', views.publish_all_submissions, name='publish_all_submissions'),
    path('admin/submissions/unpublish-all/', views.unpublish_all_submissions, name='unpublish_all_submissions'),

    # ── Notices ───────────────────────────────────────────────
    path('notices/', views.notice_list, name='notice_list'),
    path('admin/notice/add/', views.add_notice, name='add_notice'),
    path('admin/notice/<int:notice_id>/delete/', views.delete_notice, name='delete_notice'),
    path('admin/notice/delete-all/', views.delete_all_notices, name='delete_all_notices'),
    path('notices/mark-read/', views.mark_notices_read, name='mark_read'),

    # ── Resources ─────────────────────────────────────────────
    path('resources/', views.resource_list, name='resource_list'),
    path('admin/resource/add/', views.add_resource, name='add_resource'),
    path('admin/resource/<int:resource_id>/delete/', views.delete_resource, name='delete_resource'),
    path('admin/resource/delete-session/', views.delete_session, name='delete_session'),

    # ── Teachers ──────────────────────────────────────────────
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('students/', views.student_list, name='student_list'),
    path('student/<int:user_id>/delete/', views.delete_student, name='delete_student'),
    path('admin/student/<int:user_id>/progress/', views.admin_student_progress, name='admin_student_progress'),
    path('admin/student/<int:user_id>/bonus-marks/', views.admin_adjust_bonus_marks, name='admin_adjust_bonus_marks'),

    # ── Student Quiz Flow ─────────────────────────────────────
    path('quiz/<int:quiz_id>/start/', views.start_quiz, name='start_quiz'),
    path('quiz/<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),

    # ── Expired Quiz ──────────────────────────────────────────
    path('quiz/<int:quiz_id>/expired/', views.expired_quiz_answers, name='expired_quiz_answers'),
    path('result/<int:attempt_id>/', views.quiz_result, name='quiz_result'),

    # ── Leaderboard ───────────────────────────────────────────
    path('leaderboard/', views.leaderboard, name='leaderboard'),

    # ── Admin Score Adjust ────────────────────────────────────
    path('attempt/<int:attempt_id>/adjust-score/', views.adjust_score, name='adjust_score'),

    # ── AJAX Endpoints ────────────────────────────────────────
    path('quiz/save-answer/', views.save_answer, name='save_answer'),
    path('quiz/submit/', views.submit_quiz, name='submit_quiz'),
    path('quiz/log-warning/', views.log_warning, name='log_warning'),

    # ── Attendance ─────────────────────────────────────────────
    path('admin/attendance/', views.attendance_dashboard, name='attendance_dashboard'),
    path('admin/attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('admin/attendance/report/', views.attendance_report, name='attendance_report'),
    path('admin/fix-all-penalties/', views.fix_all_penalties, name='fix_all_penalties'),
    path('resource/<int:resource_id>/view/', views.view_resource_file, name='view_resource_file'),
]