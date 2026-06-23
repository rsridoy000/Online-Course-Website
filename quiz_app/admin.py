from django.contrib import admin
from .models import (
    Quiz, Question, Option, StudentAttempt, StudentAnswer, 
    WarningLog, Teacher, StudentProfile,
    Assignment, AssignmentSubmission, Notice, Resource, 
    ActivityLog, SessionReport
)

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'time_limit', 'created_at')
    search_fields = ('title',)
    ordering = ('-created_at',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'order')
    search_fields = ('text', 'quiz__title')
    list_filter = ('quiz',)
    ordering = ('quiz', 'order')

@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    search_fields = ('text', 'question__text')
    list_filter = ('is_correct',)

@admin.register(StudentAttempt)
class StudentAttemptAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'quiz', 'score', 'total_questions', 'started_at', 'is_submitted')
    search_fields = ('student_name', 'quiz__title')
    list_filter = ('quiz', 'is_submitted', 'started_at')
    ordering = ('-started_at',)
    readonly_fields = ('session_id', 'started_at', 'submitted_at')

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'selected_option')
    search_fields = ('attempt__student_name', 'question__text')
    list_filter = ('attempt__quiz',)

@admin.register(WarningLog)
class WarningLogAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'warning_type', 'timestamp', 'ip_address')
    search_fields = ('attempt__student_name', 'warning_type')
    list_filter = ('warning_type', 'timestamp')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'ip_address', 'user_agent')

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'department', 'status', 'order')
    list_editable = ('status', 'order')
    search_fields = ('name', 'designation', 'department')
    list_filter = ('status', 'department')

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'phone_number', 'attendance_count')
    search_fields = ('user__username', 'user__email', 'student_id')

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'deadline', 'total_marks')
    search_fields = ('title',)

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'marks', 'is_graded', 'submitted_at')
    list_filter = ('is_graded', 'assignment')
    search_fields = ('student__username', 'assignment__title')

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'is_active')
    list_filter = ('is_active',)

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at')
    list_filter = ('category',)

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'action')



@admin.register(SessionReport)
class SessionReportAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'quiz', 'assignment', 'generated_at')
    list_filter = ('report_type', 'generated_at')
    readonly_fields = ('generated_at',)

