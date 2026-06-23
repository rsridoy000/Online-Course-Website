from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import os
from django.conf import settings
from django.core.files.storage import default_storage

# Use Raw storage for Cloudinary in production to support HTML/CSS/JS/ZIP etc.
# MediaCloudinaryStorage defaults to 'image' which fails for non-image files.
if os.environ.get('VERCEL') or not settings.DEBUG:
    try:
        from cloudinary_storage.storage import RawMediaCloudinaryStorage
        resource_storage = RawMediaCloudinaryStorage()
    except ImportError:
        resource_storage = default_storage
else:
    resource_storage = default_storage


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    time_limit = models.IntegerField(default=30)
    start_time = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        if self.expires_at is None:
            return False
        now = timezone.now()
        # Make sure both are timezone-aware for comparison
        if timezone.is_naive(self.expires_at):
            import pytz
            bd_tz = pytz.timezone('Asia/Dhaka')
            expires_aware = bd_tz.localize(self.expires_at)
            return now > expires_aware
        return now > self.expires_at

    def is_upcoming(self):
        if not self.start_time:
            return False
        return timezone.now() < self.start_time

    class Meta:
        verbose_name_plural = "Quizzes"

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.question.text[:50]} - {self.text[:50]}"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.IntegerField(unique=True, null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    bio = models.TextField(max_length=500, null=True, blank=True)
    attendance_count = models.IntegerField(default=0)
    bonus_marks = models.IntegerField(default=0) # Overall bonus
    quiz_bonus_marks = models.IntegerField(default=0)
    assignment_bonus_marks = models.IntegerField(default=0)
    attendance_bonus_marks = models.IntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)
    view_timestamps = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_online(self):
        if self.last_activity:
            now = timezone.now()
            return now < self.last_activity + timezone.timedelta(minutes=5)
        return False

    def save(self, *args, **kwargs):
        if not self.student_id and not self.user.is_staff:
            from django.db.models import Max
            max_id = StudentProfile.objects.aggregate(Max('student_id'))['student_id__max']
            if max_id is None:
                self.student_id = 101
            else:
                self.student_id = max_id + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} (ID: {self.student_id})"

    def get_avatar_letter(self):
        name = self.user.get_full_name() or self.user.email
        return name[0].upper() if name else '?'

    def get_masked_email(self):
        email = self.user.email
        if not email or '@' not in email:
            return "---"
        try:
            user_part, domain_part = email.split('@')
            if len(user_part) <= 2:
                masked_user = user_part + "***"
            else:
                masked_user = user_part[:2] + "***"
            return f"{masked_user}@{domain_part}"
        except ValueError:
            return email


class Assignment(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements_file = models.FileField(upload_to='assignments/requirements/', null=True, blank=True)
    deadline = models.DateTimeField()
    total_marks = models.IntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def is_deadline_passed(self):
        now = timezone.now()
        if self.deadline:
            if timezone.is_naive(self.deadline):
                import pytz
                bd_tz = pytz.timezone('Asia/Dhaka')
                deadline_aware = bd_tz.localize(self.deadline)
                return now > deadline_aware
            return now > self.deadline
        return False

class AssignmentSubmission(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='assignments/submissions/', null=True, blank=True)
    drive_link = models.URLField(max_length=500, null=True, blank=True)
    marks = models.IntegerField(default=0)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_graded = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'assignment')

    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"


class Notice(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notices')
    publish_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-publish_at']

    def __str__(self):
        return self.title

class NoticeAttachment(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='notices/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_image(self):
        if self.file:
            extension = os.path.splitext(self.file.name)[1].lower()
            return extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return False

    @property
    def is_pdf(self):
        if self.file:
            extension = os.path.splitext(self.file.name)[1].lower()
            return extension == '.pdf'
        return False

    def __str__(self):
        return f"Attachment for {self.notice.title}"

class ReadNotice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='read_notices')
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='readers')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'notice')

    def __str__(self):
        return f"{self.user.username} read {self.notice.title}"


class Resource(models.Model):
    CATEGORY_CHOICES = [
        ('recording', 'Class Recording'),
        ('code', 'Code File'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('pdf', 'PDF/Doc'),
    ]
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    file = models.FileField(upload_to='resources/', storage=resource_storage, null=True, blank=True)
    video_url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True)
    resource_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_title(self):
        if self.category == 'code' and ' - ' in self.title:
            return self.title.split(' - ')[-1]
        return self.title

    def __str__(self):
        return f"[{self.category}] {self.title}"


class StudentAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='attempts')
    student_name = models.CharField(max_length=200)
    session_id = models.CharField(max_length=100, unique=True)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    is_submitted = models.BooleanField(default=False)
    question_order = models.JSONField(default=list, blank=True)
    tab_switch_count = models.IntegerField(default=0)
    is_disqualified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student_name} - {self.quiz.title}"

    def calculate_score(self):
        if self.is_disqualified:
            self.score = 0
        else:
            correct_count = sum(1 for a in self.answers.all() if a.selected_option.is_correct)
            self.score = correct_count
            
        self.total_questions = self.quiz.questions.count()
        self.is_submitted = True
        self.submitted_at = timezone.now()
        self.save()
        return self.score


class StudentAnswer(models.Model):
    attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"{self.attempt.student_name} - Q{self.question.order}"


class WarningLog(models.Model):
    WARNING_TYPES = [
        ('tab_switch', 'Tab Switch'),
        ('page_refresh', 'Page Refresh'),
        ('page_exit', 'Page Exit'),
        ('focus_lost', 'Focus Lost'),
    ]

    attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='warnings')
    warning_type = models.CharField(max_length=20, choices=WARNING_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-timestamp']

class Teacher(models.Model):
    STATUS_CHOICES = [
        ('Online', 'Online'),
        ('In Class', 'In Class'),
        ('Offline', 'Offline'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile', null=True, blank=True)
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    office_hours = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Offline')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @property
    def status_color(self):
        colors = {
            'Online': '#22c55e',
            'In Class': '#f59e0b',
            'Offline': '#64748b',
        }
        return colors.get(self.status, '#64748b')

    def get_profile_image(self):
        if self.user:
            try:
                if self.user.student_profile and self.user.student_profile.profile_image:
                    return self.user.student_profile.profile_image.url
            except Exception:
                pass
        return None

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action}"




class SessionReport(models.Model):
    REPORT_TYPES = [
        ('quiz', 'Quiz Report'),
        ('assignment', 'Assignment Report'),
    ]
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    report_file = models.FileField(upload_to='reports/')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        activity = self.quiz.title if self.report_type == 'quiz' else self.assignment.title
        return f"{self.report_type.capitalize()} Report: {activity}"

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.user.first_name} - {self.date} - {self.status}"


# --- Automated Announcements Signals ---

@receiver(post_save, sender=Assignment)
def auto_announce_assignment(sender, instance, created, **kwargs):
    action = "posted" if created else "updated"
    # Format deadline nicely
    deadline = instance.deadline
    if isinstance(deadline, str):
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(deadline)
        if parsed:
            deadline = parsed
            
    try:
        deadline_str = deadline.strftime('%d/%m/%Y, %I:%M %p') if deadline and hasattr(deadline, 'strftime') else str(deadline) if deadline else "N/A"
    except:
        deadline_str = "N/A"

    from django.urls import reverse
    link = reverse('assignment_detail', kwargs={'assignment_id': instance.id})
    
    Notice.objects.create(
        title=f"Assignment {action.capitalize()}: {instance.title}",
        content=f"Assignment '{instance.title}' has been {action}. Submission Deadline: {deadline_str}.",
        link=link
    )

@receiver(post_save, sender=Resource)
def auto_announce_resource(sender, instance, created, **kwargs):
    action = "uploaded" if created else "updated"
    from django.urls import reverse
    link = reverse('resource_list')
    
    Notice.objects.create(
        title=f"Resource {action.capitalize()}: {instance.title}",
        content=f"A new {instance.get_category_display()} titled '{instance.title}' has been {action}.",
        link=link
    )

@receiver(post_save, sender=Quiz)
def auto_announce_quiz(sender, instance, created, **kwargs):
    if created or (instance.is_published and not Notice.objects.filter(title__icontains=f"Quiz: {instance.title}").exists()):
        action = "created" if created else "published"
        if instance.is_published:
            from django.urls import reverse
            link = reverse('start_quiz', kwargs={'quiz_id': instance.id})
            
            Notice.objects.create(
                title=f"Quiz {action.capitalize()}: {instance.title}",
                content=f"A new quiz '{instance.title}' is now available. Time Limit: {instance.time_limit} minutes.",
                link=link
            )

@receiver(post_save, sender=Attendance)
@receiver(models.signals.post_delete, sender=Attendance)
def update_student_attendance_count(sender, instance, **kwargs):
    profile = instance.student
    count = Attendance.objects.filter(student=profile, status='Present').count()
    if profile.attendance_count != count:
        profile.attendance_count = count
        profile.save(update_fields=['attendance_count'])

    