from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import os
import json
import uuid
import random
from django.core.mail import send_mail
from django.conf import settings
import threading

from .models import (
    Quiz, Question, Option, StudentAttempt,
    StudentAnswer, WarningLog, StudentProfile,
    Assignment, AssignmentSubmission, Notice, NoticeAttachment, Resource,
    ActivityLog, SessionReport, ReadNotice, Attendance, Teacher
)


# ==================== CENTRALIZED SCORING HELPER ====================
def calculate_student_score(student):
    """Single source of truth for all mark calculations across the site.
    Returns a dict with breakdown and total.
    Formula: (Quiz best scores + quiz_bonus) + (Attendance*5 + att_bonus) + (Assignment marks + ass_bonus) + overall_bonus
    """
    from django.db.models import Max
    profile = student.student_profile

    # 1. Quiz Score (best attempt per quiz) + quiz bonus
    s_attempts = StudentAttempt.objects.filter(student=student, is_submitted=True)
    quiz_base = sum(item['max_score'] for item in s_attempts.values('quiz').annotate(max_score=Max('score')))
    quiz_score = quiz_base + profile.quiz_bonus_marks

    # 2. Attendance Score (count * 5) + attendance bonus
    att_score = (profile.attendance_count * 5) + profile.attendance_bonus_marks

    # 3. Assignment Score (graded + published) + assignment bonus
    ass_base = sum(sub.marks for sub in AssignmentSubmission.objects.filter(
        student=student, is_graded=True, is_published=True
    ))
    ass_score = ass_base + profile.assignment_bonus_marks

    # 4. Overall bonus
    total = quiz_score + att_score + ass_score + profile.bonus_marks

    return {
        'total': total,
        'quiz_score': quiz_score,
        'att_score': att_score,
        'ass_score': ass_score,
        'bonus': profile.bonus_marks,
    }


def get_all_student_scores():
    """
    Computes all student scores and rankings in bulk to avoid N+1 query problem.
    Returns a dict mapping student_id to score breakdown.
    """
    from collections import defaultdict
    from django.db.models import Max
    
    # 1. Fetch all students
    students = User.objects.filter(student_profile__isnull=False).exclude(is_staff=True).select_related('student_profile')
    
    # 2. Fetch all submitted attempts
    attempts = StudentAttempt.objects.filter(is_submitted=True).only('student_id', 'quiz_id', 'score')
    attempts_by_student = defaultdict(list)
    for a in attempts:
        if a.student_id:
            attempts_by_student[a.student_id].append(a)
            
    # 3. Fetch all graded and published assignment submissions
    submissions = AssignmentSubmission.objects.filter(is_graded=True, is_published=True).only('student_id', 'assignment_id', 'marks')
    submissions_by_student = defaultdict(list)
    for sub in submissions:
        if sub.student_id:
            submissions_by_student[sub.student_id].append(sub)
            
    # 4. Compute scores for all students
    results = {}
    for s in students:
        profile = s.student_profile
        
        # Calculate quiz base (best score per quiz) in memory
        student_attempts = attempts_by_student[s.id]
        best_quiz_scores = {}
        for a in student_attempts:
            best_quiz_scores[a.quiz_id] = max(best_quiz_scores.get(a.quiz_id, 0), a.score)
        quiz_base = sum(best_quiz_scores.values())
        quiz_score = quiz_base + profile.quiz_bonus_marks
        
        # Calculate attendance score
        att_score = (profile.attendance_count * 5) + profile.attendance_bonus_marks
        
        # Calculate assignment base
        student_submissions = submissions_by_student[s.id]
        ass_base = sum(sub.marks for sub in student_submissions)
        ass_score = ass_base + profile.assignment_bonus_marks
        
        # Total
        total = quiz_score + att_score + ass_score + profile.bonus_marks
        
        results[s.id] = {
            'total': total,
            'quiz_score': quiz_score,
            'att_score': att_score,
            'ass_score': ass_score,
            'bonus': profile.bonus_marks,
            'quiz_count': len(student_attempts),
        }
    return results


def log_activity(user, action, description=""):
    """Helper function to log user activities."""
    if user.is_authenticated:
        ActivityLog.objects.create(
            user=user,
            action=action,
            description=description
        )


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def send_email_async(subject, message, recipient_list, html_message=None):
    """Sends email directly. (Synchronous for Vercel reliability)"""
    try:
        send_mail(
            subject, 
            message, 
            settings.EMAIL_DEFAULT_FROM_EMAIL, 
            recipient_list, 
            html_message=html_message, 
            fail_silently=False
        )
    except Exception as e:
        print(f"Email error: {str(e)}")
        raise e


def get_user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '')


def get_user_ranking_stats(user):
    from django.db.models import Max
    all_students = User.objects.filter(student_profile__isnull=False).exclude(is_staff=True).select_related('student_profile')
    
    rank_list = []
    user_total = 0
    
    for s in all_students:
        # 1. Quiz Score (Best per unique quiz)
        s_attempts = StudentAttempt.objects.filter(student=s, is_submitted=True)
        q_score = sum(item['max_score'] for item in s_attempts.values('quiz').annotate(max_score=Max('score')))
        
        # 2. Attendance Score (Calculated from Attendance records)
        from .models import Attendance
        att_count = Attendance.objects.filter(student=s.student_profile, status='Present').count()
        att_score = (att_count * 5)
        
        # 3. Assignment Score (Only include if manually published)
        ass_score = sum(sub.marks for sub in AssignmentSubmission.objects.filter(
            student=s, 
            is_graded=True,
            is_published=True
        ))
        
        # 4. Bonus
        bonus = s.student_profile.bonus_marks
        
        total = q_score + att_score + ass_score + bonus
        if s == user:
            user_total = total
        
        rank_list.append({'id': s.id, 'total': total})
    
    rank_list.sort(key=lambda x: -x['total'])
    rank = next((i for i, x in enumerate(rank_list, 1) if x['id'] == user.id), 999)
    
    return user_total, rank


# ==================== STUDENT AUTH ====================

def student_register(request):
    if request.user.is_authenticated and not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        errors = {}

        if not full_name:
            errors['full_name'] = 'Name is required.'
        if not email:
            errors['email'] = 'Email is required.'
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'This email is already registered.'
        if len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters.'
        if password != password2:
            errors['password2'] = 'Passwords do not match.'

        if errors:
            return render(request, 'student_register.html', {'errors': errors, 'form_data': request.POST})

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        
        # Store in session
        request.session['reg_data'] = {
            'full_name': full_name,
            'email': email,
            'password': password
        }
        request.session['reg_otp'] = otp
        request.session['otp_expiry'] = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()

        # Send HTML Mail
        subject = f"Verify your Liquid_Triple_R Account - {otp}"
        html_message = render_to_string('emails/otp_email.html', {
            'full_name': full_name,
            'otp': otp
        })
        
        try:
            send_email_async(
                subject,
                f"Your OTP is {otp}", # Fallback plain text
                [email],
                html_message=html_message
            )
            return redirect('verify_otp')
        except Exception as e:
            errors['email'] = f"Failed to send OTP. Please check your email or try again. Error: {str(e)}"
            return render(request, 'student_register.html', {'errors': errors, 'form_data': request.POST})

    return render(request, 'student_register.html')


from django.db import transaction

def verify_otp(request):
    reg_data = request.session.get('reg_data')
    correct_otp = request.session.get('reg_otp')
    otp_expiry = request.session.get('otp_expiry')
    
    if not reg_data or not correct_otp:
        return redirect('student_register')

    if request.method == 'POST':
        entered_otp = "".join([
            request.POST.get('otp1', ''),
            request.POST.get('otp2', ''),
            request.POST.get('otp3', ''),
            request.POST.get('otp4', ''),
            request.POST.get('otp5', ''),
            request.POST.get('otp6', '')
        ])
        
        if not entered_otp:
            entered_otp = request.POST.get('otp', '')

        # 1. Check Expiry
        if otp_expiry:
            expiry_dt = parse_datetime(otp_expiry)
            if expiry_dt and timezone.now() > expiry_dt:
                messages.error(request, "OTP has expired. Please request a new one.")
                return redirect('student_register')

        # 2. Verify OTP
        if entered_otp == correct_otp:
            try:
                # Create User and Profile within a transaction
                with transaction.atomic():
                    full_name = reg_data['full_name']
                    email = reg_data['email']
                    password = reg_data['password']
                    parts = full_name.split()
                    
                    # Check again if user exists to prevent Race Condition
                    if User.objects.filter(username=email).exists():
                        messages.error(request, "An account with this email already exists.")
                        return redirect('student_login')

                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=parts[0],
                        last_name=' '.join(parts[1:]) if len(parts) > 1 else '',
                    )
                    # This will trigger StudentProfile.save() and its student_id logic
                    StudentProfile.objects.create(user=user)
                
                # Clear session (outside of transaction.atomic)
                for key in ['reg_data', 'reg_otp', 'otp_expiry']:
                    if key in request.session:
                        del request.session[key]
                
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"Welcome {full_name}! Your account has been created.")
                return redirect('home')
            except Exception as e:
                # Any error (like IntegrityError) will trigger rollback of User creation
                import traceback
                traceback.print_exc()
                return render(request, 'otp_verify.html', {
                    'error': f"Error creating account: {str(e)}", 
                    'email': reg_data['email']
                })
        else:
            return render(request, 'otp_verify.html', {
                'error': 'Invalid OTP. Please try again.', 
                'email': reg_data['email']
            })

    return render(request, 'otp_verify.html', {'email': reg_data['email']})


def resend_otp(request):
    reg_data = request.session.get('reg_data')
    if not reg_data:
        return redirect('student_register')

    # Generate NEW OTP
    otp = str(random.randint(100000, 999999))
    request.session['reg_otp'] = otp
    request.session['otp_expiry'] = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()

    # Send HTML Mail
    subject = f"Verify your Liquid_Triple_R Account (New OTP) - {otp}"
    html_message = render_to_string('emails/otp_email.html', {
        'full_name': reg_data['full_name'],
        'otp': otp
    })
    
    try:
        send_email_async(
            subject,
            f"Your new OTP is {otp}", 
            [reg_data['email']],
            html_message=html_message
        )
        messages.success(request, "A new OTP has been sent to your email.")
    except Exception as e:
        messages.error(request, f"Failed to send OTP: {str(e)}")

    return redirect('verify_otp')


def student_password_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        try:
            # Use filter().first() to avoid MultipleObjectsReturned if duplicates exist
            user = User.objects.filter(email=email).first()
            if not user:
                raise User.DoesNotExist
            
            otp = str(random.randint(100000, 999999))
            
            # Store in session
            request.session['reset_email'] = email
            request.session['reset_otp'] = otp
            
            # Send HTML Mail
            subject = f"Password Reset OTP - {otp}"
            html_message = render_to_string('emails/password_reset_email.html', {
                'otp': otp
            })
            
            send_email_async(
                subject,
                f"Your password reset OTP is {otp}",
                [email],
                html_message=html_message
            )
            return redirect('student_password_reset_verify')
        except User.DoesNotExist:
            return render(request, 'student_password_reset.html', {'error': 'No account found with this email.'})
            
    return render(request, 'student_password_reset.html')


def student_password_reset_verify(request):
    email = request.session.get('reset_email')
    correct_otp = request.session.get('reset_otp')
    
    if not email or not correct_otp:
        return redirect('student_password_reset')

    if request.method == 'POST':
        entered_otp = "".join([
            request.POST.get('otp1', ''),
            request.POST.get('otp2', ''),
            request.POST.get('otp3', ''),
            request.POST.get('otp4', ''),
            request.POST.get('otp5', ''),
            request.POST.get('otp6', '')
        ])
        
        if entered_otp == correct_otp:
            request.session['otp_verified'] = True
            return redirect('student_password_reset_confirm')
        else:
            return render(request, 'student_password_reset_verify.html', {'error': 'Invalid OTP.', 'email': email})

    return render(request, 'student_password_reset_verify.html', {'email': email})


def student_password_reset_confirm(request):
    email = request.session.get('reset_email')
    if not email or not request.session.get('otp_verified'):
        return redirect('student_password_reset')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        
        if len(password) < 6:
            return render(request, 'student_password_reset_confirm.html', {'error': 'Password must be at least 6 characters.'})
        if password != password2:
            return render(request, 'student_password_reset_confirm.html', {'error': 'Passwords do not match.'})
            
        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(password)
            user.save()
        
        # Clear session
        del request.session['reset_email']
        del request.session['reset_otp']
        del request.session['otp_verified']
        
        return redirect('student_login')

    return render(request, 'student_password_reset_confirm.html')


def resend_password_reset_otp(request):
    reg_data = request.session.get('reset_email')
    if not reg_data:
        return redirect('student_password_reset')

    email = request.session.get('reset_email')
    otp = str(random.randint(100000, 999999))
    request.session['reset_otp'] = otp

    subject = f"Password Reset OTP - {otp}"
    html_message = render_to_string('emails/password_reset_email.html', {'otp': otp})
    send_email_async(
        subject,
        f"Your new password reset OTP is {otp}",
        [email],
        html_message=html_message
    )
    return redirect('student_password_reset_verify')


def student_login(request):
    if request.user.is_authenticated and not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if not user.is_staff:
                login(request, user)
                return redirect('home')
            else:
                return render(request, 'student_login.html', {
                    'error': 'This is an Admin account. Please use the Admin Login portal.',
                    'is_admin_error': True
                })
        else:
            return render(request, 'student_login.html', {'error': 'Invalid email or password.'})

    return render(request, 'student_login.html')


def student_logout(request):
    logout(request)
    return redirect('student_login')


def student_profile(request):
    if not request.user.is_authenticated or request.user.is_staff:
        return redirect('student_login')

    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if 'profile_image' in request.FILES:
            try:
                profile.profile_image = request.FILES['profile_image']
                profile.save()
                messages.success(request, "Profile image updated successfully!")
            except Exception as e:
                messages.error(request, f"Error uploading image: {str(e)}")
        
        # Save other fields if needed
        full_name = request.POST.get('full_name', '').strip()
        if full_name:
            parts = full_name.split()
            request.user.first_name = parts[0]
            request.user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
            request.user.save()
            messages.success(request, "Name updated successfully!")

        return redirect('student_profile')

    attempts = StudentAttempt.objects.filter(
        student=request.user, is_submitted=True
    ).order_by('-submitted_at')

    # Add percentage to each attempt for easier template coloring
    for attempt in attempts:
        if attempt.total_questions > 0:
            attempt.percentage = round((attempt.score / attempt.total_questions) * 100)
        else:
            attempt.percentage = 0

    # --- Unified Ranking System (Matches Leaderboard) ---
    all_scores = get_all_student_scores()
    temp = [{'student_id': sid, 'total_score': info['total']} for sid, info in all_scores.items()]
    temp.sort(key=lambda x: -x['total_score'])
    my_rank = next((i for i, x in enumerate(temp, 1) if x['student_id'] == request.user.id), None)

    # --- Unified Raw Mark Scoring System (uses centralized helper) ---
    my_sc = all_scores.get(request.user.id, {'quiz_score': 0, 'att_score': 0, 'ass_score': 0, 'total': 0})
    quiz_score = my_sc['quiz_score']
    attendance_score = my_sc['att_score']
    assignment_score = my_sc['ass_score']
    total_marks = my_sc['total']

    assignment_submissions = AssignmentSubmission.objects.filter(
        student=request.user
    ).select_related('assignment').order_by('-submitted_at')

    # Calculate total tab switches/warnings across all quizzes
    total_tab_switches = WarningLog.objects.filter(attempt__student=request.user).count()

    context = {
        'student': request.user,
        'profile': profile,
        'attempts': attempts,
        'assignment_submissions': assignment_submissions,
        'my_rank': my_rank,
        'total_students': len(temp),
        'total_marks': total_marks,
        'attendance_count': profile.attendance_count,
        'attendance_score': attendance_score,
        'quiz_score': quiz_score,
        'assignment_score': assignment_score,
        'total_tab_switches': total_tab_switches,
    }
    return render(request, 'student_profile.html', context)


# ==================== ADMIN VIEWS ====================

def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()
        password = request.POST.get('password', '')
        
        # Hardcoded check for admin users as requested
        admin_usernames = ['admin_refat', 'admin_ridoy', 'admin_rafi']
        if password == '730323':
            if username in admin_usernames:
                user = User.objects.filter(username=username).first()
                if not user:
                    # Automatically create the user if it doesn't exist in this database
                    user = User.objects.create_superuser(username=username, email=f"{username}@example.com", password=password)
                
                if user.is_staff:
                    # Explicitly set the backend for manual login
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    login(request, user)
                    return redirect('admin_dashboard')
                else:
                    return render(request, 'admin_login.html', {'error': f'User {username} is not a staff member'})
            # If password is correct but username not in list, continue to authenticate

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect('admin_dashboard')
            else:
                return render(request, 'admin_login.html', {'error': 'This is a Student account. Admins only.'})
        else:
            error_msg = 'Invalid credentials or account does not exist.'
            return render(request, 'admin_login.html', {'error': error_msg})

    return render(request, 'admin_login.html')


@login_required(login_url='admin_login')
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    quizzes = Quiz.objects.all().order_by('-created_at')
    assignments = Assignment.objects.all().order_by('-created_at')
    all_attempts = StudentAttempt.objects.all().select_related('student__student_profile', 'quiz').order_by('-started_at')
    all_submissions = AssignmentSubmission.objects.all().select_related('student', 'assignment').order_by('-submitted_at')
    all_warnings = WarningLog.objects.all().select_related('attempt__student__student_profile', 'attempt__quiz').order_by('-timestamp')

    # Determine the currently active/running quiz
    running_quiz = None
    for q in quizzes:
        if q.is_published and not q.is_expired():
            running_quiz = q
            break
    if not running_quiz:
        running_quiz = quizzes.first()

    # Determine the currently active/running assignment
    running_assignment = None
    for a in assignments:
        if not a.is_deadline_passed:
            running_assignment = a
            break
    if not running_assignment:
        running_assignment = assignments.first()

    latest_quiz_attempts_count = StudentAttempt.objects.filter(quiz=running_quiz, is_submitted=True).count() if running_quiz else 0
    latest_assignment_attempts_count = AssignmentSubmission.objects.filter(assignment=running_assignment).count() if running_assignment else 0
    running_quiz_warnings_count = WarningLog.objects.filter(attempt__quiz=running_quiz).count() if running_quiz else 0

    context = {
        'quizzes': quizzes,
        'assignments': assignments,
        'all_attempts': all_attempts,
        'all_submissions': all_submissions,
        'all_warnings': all_warnings,
        'total_quizzes': quizzes.count(),
        'total_assignments': assignments.count(),
        'total_attempts': all_attempts.count(),
        'total_submissions': all_submissions.count(),
        'total_warnings': all_warnings.count(),
        'total_students': User.objects.filter(student_profile__isnull=False, is_staff=False, is_superuser=False).count(),
        'latest_quiz_attempts_count': latest_quiz_attempts_count,
        'latest_assignment_attempts_count': latest_assignment_attempts_count,
        'running_quiz_warnings_count': running_quiz_warnings_count,
        'running_quiz': running_quiz,
        'running_assignment': running_assignment,
    }
    return render(request, 'admin_dashboard.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def admin_cleanup_duplicates(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
    student_names = StudentAttempt.objects.values_list('student_name', flat=True).distinct()
    total_deleted = 0
    details = []
    
    for s_name in student_names:
        if not s_name:
            continue
        quizzes = StudentAttempt.objects.filter(student_name=s_name).values_list('quiz', flat=True).distinct()
        for quiz_id in quizzes:
            # Find all unsubmitted (In Progress) attempts for this student and quiz
            attempts = list(StudentAttempt.objects.filter(
                student_name=s_name, 
                quiz_id=quiz_id, 
                is_submitted=False
            ).order_by('-started_at'))
            
            if len(attempts) > 1:
                # Sort attempts by how many answers they have (most answers first), then by latest started_at
                attempts.sort(key=lambda a: (a.answers.count(), a.started_at), reverse=True)
                
                # Keep the best one (index 0)
                keep_attempt = attempts[0]
                delete_attempts = attempts[1:]
                
                for da in delete_attempts:
                    details.append(f"Deleted duplicate attempt ID {da.id} for {s_name} (Quiz ID: {quiz_id})")
                    da.delete()
                    total_deleted += 1
                    
    return JsonResponse({
        'success': True,
        'deleted_count': total_deleted,
        'details': details
    })


@login_required(login_url='admin_login')
def quiz_detail(request, quiz_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    quiz = get_object_or_404(Quiz, id=quiz_id)
    context = {
        'quiz': quiz,
        'questions': quiz.questions.all().order_by('order'),
        'attempts': quiz.attempts.all().order_by('-started_at'),
    }
    return render(request, 'quiz_detail.html', context)


@login_required(login_url='admin_login')
def create_quiz(request):
    if not request.user.is_staff:
        return redirect('admin_login')
    if request.method == 'POST':
        expires_at_str = request.POST.get('expires_at', '').strip()
        expires_at = None
        if expires_at_str:
            from django.utils.dateparse import parse_datetime
            expires_at = parse_datetime(expires_at_str)
        quiz = Quiz.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            time_limit=int(request.POST.get('time_limit', 30)),
            expires_at=expires_at,
        )
        return redirect('quiz_detail', quiz_id=quiz.id)
    return render(request, 'create_quiz.html')


@login_required(login_url='admin_login')
def edit_quiz(request, quiz_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == 'POST':
        expires_at_str = request.POST.get('expires_at', '').strip()
        expires_at = None
        if expires_at_str:
            from django.utils.dateparse import parse_datetime
            expires_at = parse_datetime(expires_at_str)
        quiz.title = request.POST.get('title')
        quiz.description = request.POST.get('description')
        quiz.time_limit = int(request.POST.get('time_limit', 30))
        quiz.expires_at = expires_at
        quiz.save()
        return redirect('quiz_detail', quiz_id=quiz.id)
    return render(request, 'edit_quiz.html', {'quiz': quiz})


@login_required(login_url='admin_login')
def delete_quiz(request, quiz_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    get_object_or_404(Quiz, id=quiz_id).delete()
    return redirect('admin_dashboard')


@login_required(login_url='admin_login')
def toggle_quiz_publish(request, quiz_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    was_published = quiz.is_published
    quiz.is_published = not quiz.is_published
    quiz.save()
    
    if not was_published and quiz.is_published:
        messages.success(request, f"Quiz '{quiz.title}' published successfully! Students have been notified.")
    elif was_published and not quiz.is_published:
        messages.success(request, f"Quiz '{quiz.title}' is now hidden from students.")
        
    return redirect('quiz_detail', quiz_id=quiz_id)


@login_required(login_url='admin_login')
def add_question(request, quiz_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == 'POST':
        question = Question.objects.create(
            quiz=quiz,
            text=request.POST.get('question_text'),
            order=quiz.questions.count() + 1
        )
        for i in range(4):
            Option.objects.create(
                question=question,
                text=request.POST.get(f'option_{i+1}'),
                is_correct=request.POST.get('correct_option') == str(i+1)
            )
        return redirect('quiz_detail', quiz_id=quiz.id)
    return render(request, 'add_question.html', {'quiz': quiz})


@login_required(login_url='admin_login')
def edit_question(request, question_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    question = get_object_or_404(Question, id=question_id)
    if request.method == 'POST':
        question.text = request.POST.get('question_text')
        question.save()
        for i, option in enumerate(question.options.all()):
            option.text = request.POST.get(f'option_{i+1}')
            option.is_correct = request.POST.get('correct_option') == str(i+1)
            option.save()
        return redirect('quiz_detail', quiz_id=question.quiz.id)
    return render(request, 'edit_question.html', {'question': question, 'options': question.options.all()})


@login_required(login_url='admin_login')
def delete_question(request, question_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    question = get_object_or_404(Question, id=question_id)
    quiz_id = question.quiz.id
    question.delete()
    return redirect('quiz_detail', quiz_id=quiz_id)


@login_required(login_url='admin_login')
def view_attempt(request, attempt_id):
    if not request.user.is_staff:
        return redirect('admin_login')
    attempt = get_object_or_404(StudentAttempt, id=attempt_id)
    answers = attempt.answers.all().select_related('question', 'selected_option')
    questions_with_answers = []
    for question in attempt.quiz.questions.all():
        try:
            answer = answers.get(question=question)
            questions_with_answers.append({
                'question': question,
                'student_answer': answer,
                'correct_option': question.options.filter(is_correct=True).first(),
                'is_correct': answer.selected_option.is_correct if answer.selected_option else False,
            })
        except StudentAnswer.DoesNotExist:
            questions_with_answers.append({
                'question': question,
                'student_answer': None,
                'correct_option': question.options.filter(is_correct=True).first(),
                'is_correct': False,
            })
    context = {
        'attempt': attempt,
        'questions_with_answers': questions_with_answers,
        'warnings': attempt.warnings.all().order_by('timestamp'),
    }
    return render(request, 'view_attempt.html', context)


@login_required(login_url='admin_login')
@csrf_exempt
@require_http_methods(["POST"])
def delete_attempt(request, attempt_id):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    attempt = get_object_or_404(StudentAttempt, id=attempt_id)
    attempt.delete()
    return JsonResponse({'success': True})


def admin_logout(request):
    logout(request)
    return redirect('admin_login')


@login_required(login_url='admin_login')
def admin_profile(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    teacher_profile = Teacher.objects.filter(user=request.user).first()

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        designation = request.POST.get('designation', '').strip()
        availability_status = request.POST.get('availability_status', '').strip()
        department = request.POST.get('department', 'Computer Science and Technology').strip()
        office_hours = request.POST.get('office_hours', '').strip()

        # Update User model
        if full_name:
            parts = full_name.split()
            request.user.first_name = parts[0]
            request.user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        if email:
            request.user.email = email
        request.user.save()

        # Update StudentProfile model
        if 'profile_image' in request.FILES:
            try:
                profile.profile_image = request.FILES['profile_image']
                profile.save()
                messages.success(request, "Profile image updated successfully!")
            except Exception as e:
                messages.error(request, f"Error uploading admin image: {str(e)}")
            
        profile.phone_number = phone_number
        profile.bio = designation # Syncing designation to bio for consistency
        try:
            profile.save()
        except Exception as e:
            messages.error(request, f"Error saving profile: {str(e)}")

        # Update or Create Teacher model
        if not teacher_profile:
            teacher_profile = Teacher.objects.create(
                user=request.user,
                name=request.user.get_full_name() or request.user.username,
                email=request.user.email,
                phone=phone_number,
                designation=designation,
                status=availability_status,
                department=department,
                office_hours=office_hours
            )
        else:
            teacher_profile.status = availability_status
            teacher_profile.name = request.user.get_full_name() or request.user.username
            teacher_profile.email = request.user.email
            teacher_profile.phone = phone_number
            teacher_profile.designation = designation
            teacher_profile.department = department
            teacher_profile.office_hours = office_hours
            teacher_profile.save()

        return redirect('admin_profile')

    total_quizzes = Quiz.objects.count()
    total_attempts = StudentAttempt.objects.filter(is_submitted=True).count()
    total_warnings = WarningLog.objects.count()

    context = {
        'admin_user': request.user,
        'profile': profile,
        'teacher_profile': teacher_profile,
        'total_quizzes': total_quizzes,
        'total_attempts': total_attempts,
        'total_warnings': total_warnings,
    }
    return render(request, 'admin_profile.html', context)


@login_required(login_url='student_login')
def remove_profile_image(request):
    """Removes the profile image for a student."""
    if request.method == 'POST':
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        if profile.profile_image:
            profile.profile_image = None
            profile.save()
    return redirect('student_profile')


@login_required(login_url='admin_login')
def remove_admin_profile_image(request):
    """Removes the profile image for an admin."""
    if not request.user.is_staff:
        return redirect('admin_login')
    if request.method == 'POST':
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        if profile.profile_image:
            profile.profile_image = None
            profile.save()
    return redirect('admin_profile')


# ==================== STUDENT QUIZ VIEWS ====================

def home(request):
    if not request.user.is_authenticated:
        return redirect('student_login')
    quizzes = Quiz.objects.filter(is_published=True).order_by('-created_at')

    submitted_quiz_ids = set(StudentAttempt.objects.filter(
        student=request.user, is_submitted=True
    ).values_list('quiz_id', flat=True))

    quiz_list = []
    for quiz in quizzes:
        attempt_id = None
        if quiz.id in submitted_quiz_ids:
            att = StudentAttempt.objects.filter(
                student=request.user, quiz=quiz, is_submitted=True
            ).first()
            if att:
                attempt_id = att.id
        quiz_list.append({
            'quiz': quiz,
            'is_submitted': quiz.id in submitted_quiz_ids,
            'is_expired': quiz.is_expired(),
            'attempt_id': attempt_id,
        })

    profile = None
    try:
        profile = request.user.student_profile
    except Exception:
        pass

    # Sort: Active (not submitted, not expired) → Submitted → Expired
    def quiz_sort_key(item):
        if item['is_submitted']:
            return 1  # Middle (Submitted)
        elif item['is_expired']:
            return 2  # Last (Expired and Not Submitted)
        else:
            return 0  # First (Active)

    quiz_list.sort(key=quiz_sort_key)

    context = {
        'quiz_list': quiz_list,
        'profile': profile,
    }
    return render(request, 'home.html', context)


def start_quiz(request, quiz_id):
    if not request.user.is_authenticated:
        return redirect('student_login')
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not request.user.is_staff:
        already_submitted = StudentAttempt.objects.filter(
            student=request.user, quiz=quiz, is_submitted=True
        ).exists()
        if already_submitted:
            return redirect('quiz_list')

        if quiz.is_expired():
            messages.error(request, "This quiz has expired and can no longer be taken.")
            return redirect('quiz_list')

        # Check for existing in-progress attempt on GET
        existing_attempt = StudentAttempt.objects.filter(
            student=request.user, quiz=quiz, is_submitted=False
        ).first()
        if existing_attempt:
            request.session['attempt_id'] = existing_attempt.id
            request.session['session_id'] = existing_attempt.session_id
            return redirect('take_quiz', quiz_id=quiz.id)

    if request.method == 'POST':
        # Double check inside POST block to prevent race conditions
        if not request.user.is_staff:
            existing_attempt = StudentAttempt.objects.filter(
                student=request.user, quiz=quiz, is_submitted=False
            ).first()
            if existing_attempt:
                request.session['attempt_id'] = existing_attempt.id
                request.session['session_id'] = existing_attempt.session_id
                return redirect('take_quiz', quiz_id=quiz.id)

        session_id = str(uuid.uuid4())
        attempt = StudentAttempt.objects.create(
            quiz=quiz,
            student=request.user,
            student_name=request.user.get_full_name() or request.user.email,
            session_id=session_id,
            total_questions=quiz.questions.count(),
        )
        request.session['attempt_id'] = attempt.id
        request.session['session_id'] = session_id
        return redirect('take_quiz', quiz_id=quiz.id)
    context = {'quiz': quiz}
    return render(request, 'start_quiz.html', context)


def take_quiz(request, quiz_id):
    if not request.user.is_authenticated:
        return redirect('student_login')
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Admin can retake quiz freely — skip submission check
    if not request.user.is_staff:
        if quiz.is_expired():
            messages.error(request, "This quiz has expired and can no longer be taken.")
            return redirect('quiz_list')

        already_submitted = StudentAttempt.objects.filter(
            student=request.user, quiz=quiz, is_submitted=True
        ).first()
        if already_submitted:
            return redirect('quiz_result', attempt_id=already_submitted.id)

    attempt_id = request.session.get('attempt_id')
    if not attempt_id:
        return redirect('start_quiz', quiz_id=quiz_id)
    attempt = get_object_or_404(StudentAttempt, id=attempt_id)
    if attempt.is_submitted:
        return redirect('quiz_result', attempt_id=attempt.id)
    if not attempt.question_order:
        questions = list(quiz.questions.values_list('id', flat=True))
        random.shuffle(questions)
        attempt.question_order = questions
        attempt.save()
    questions = Question.objects.filter(id__in=attempt.question_order)
    order_map = {q_id: idx for idx, q_id in enumerate(attempt.question_order)}
    questions = sorted(questions, key=lambda q: order_map[q.id])
    total_questions = len(questions)
    context = {'quiz': quiz, 'attempt': attempt, 'questions': questions, 'total_questions': total_questions}
    return render(request, 'take_quiz.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def save_answer(request):
    try:
        data = json.loads(request.body)
        attempt = StudentAttempt.objects.get(id=data.get('attempt_id'))
        question = Question.objects.get(id=data.get('question_id'))
        option = Option.objects.get(id=data.get('option_id'))
        StudentAnswer.objects.update_or_create(
            attempt=attempt, question=question,
            defaults={'selected_option': option}
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz(request):
    try:
        data = json.loads(request.body)
        attempt = StudentAttempt.objects.get(id=data.get('attempt_id'))
        if attempt.quiz.is_expired():
            from datetime import timedelta
            grace_time = attempt.quiz.expires_at + timedelta(seconds=30)
            if timezone.now() > grace_time:
                return JsonResponse({'success': False, 'error': 'Quiz time has expired. Submission not allowed.'}, status=403)
        attempt.calculate_score()
        # Corrected Penalty Rules (1=-2, 2=-5, 3+=Disqualified)
        if attempt.tab_switch_count == 1:
            attempt.score = max(0, attempt.score - 2)
        elif attempt.tab_switch_count == 2:
            attempt.score = max(0, attempt.score - 5)
        elif attempt.tab_switch_count >= 3 or attempt.is_disqualified:
            attempt.score = 0
            attempt.is_disqualified = True
        
        attempt.save()
        
        # Log activity
        log_activity(request.user, "Completed Quiz", f"Finished quiz: {attempt.quiz.title}")

        return JsonResponse({'success': True, 'attempt_id': attempt.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def log_warning(request):
    try:
        data = json.loads(request.body)
        attempt = StudentAttempt.objects.get(id=data.get('attempt_id'))
        warning_type = data.get('warning_type')

        # Anti-Duplicate / Debounce: Check if a log was created in the last 2 seconds
        recent_log = WarningLog.objects.filter(
            attempt=attempt, 
            timestamp__gte=timezone.now() - timezone.timedelta(seconds=2)
        ).exists()

        if recent_log:
            return JsonResponse({'success': True, 'action': 'none'})

        # Force all cheat events to be 'tab_switch' for clarity
        WarningLog.objects.create(
            attempt=attempt,
            warning_type='tab_switch',
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )

        response_data = {'success': True, 'action': 'none'}

        # Count any cheat activity as a Tab Switch
        attempt.tab_switch_count += 1
        attempt.save()

        if attempt.tab_switch_count == 1:
            response_data['action'] = 'warning'
            response_data['message'] = '🚨 ট্যাব পরিবর্তন করার জন্য আপনার ২ মার্ক কাটা যাবে। ২য় বার করলে কুইজ বাতিল হবে!'
        elif attempt.tab_switch_count == 2:
            response_data['action'] = 'warning'
            response_data['message'] = '🚨 ২য় বার ট্যাব পরিবর্তন! এবার আপনার মোট ৫ মার্ক কাটা যাবে। ৩য় বার করলে কুইজ বাতিল!'
        else:
            attempt.is_disqualified = True
            attempt.score = 0
            attempt.save()
            response_data['action'] = 'disqualified'
            response_data['message'] = '🚫 কুইজ বাতিল! আপনি ২ বার ট্যাব পরিবর্তন করেছেন।'

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def fix_all_penalties(request):
    if not request.user.is_staff:
        return redirect('home')
    
    attempts = StudentAttempt.objects.all()
    updated_count = 0
    details = []

    for attempt in attempts:
        # Get all logs for this attempt ordered by timestamp
        logs = WarningLog.objects.filter(attempt=attempt).order_by('timestamp')
        
        unique_events = 0
        last_timestamp = None
        
        # Deduplicate: Only count as a new event if > 5 seconds from the last one
        for log in logs:
            if last_timestamp is None or (log.timestamp - last_timestamp).total_seconds() > 5:
                unique_events += 1
                last_timestamp = log.timestamp
        
        attempt.tab_switch_count = unique_events
        
        # Recalculate base score from answers
        correct_count = sum(1 for a in attempt.answers.all() if a.selected_option and a.selected_option.is_correct)
        attempt.score = correct_count
        
        status = "Normal"
        if unique_events >= 3:
            attempt.score = 0
            attempt.is_disqualified = True
            status = f"Disqualified ({unique_events} events)"
        elif unique_events == 2:
            attempt.score = max(0, attempt.score - 5)
            attempt.is_disqualified = False
            status = "Penalty Applied (-5 Marks)"
        elif unique_events == 1:
            attempt.score = max(0, attempt.score - 2)
            attempt.is_disqualified = False
            status = "Penalty Applied (-2 Marks)"
        else:
            attempt.is_disqualified = False
            status = "No Penalty"
        
        attempt.save()
        updated_count += 1
        details.append({
            'student': attempt.student_name,
            'quiz': attempt.quiz.title,
            'unique_warnings': unique_events,
            'total_logs_found': logs.count(),
            'final_score': attempt.score,
            'status': status
        })

    return JsonResponse({
        'success': True, 
        'message': f'Processed {updated_count} attempts with deduplication logic.',
        'details': details
    })



def expired_quiz_answers(request, quiz_id):
    if not request.user.is_authenticated:
        return redirect('student_login')
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # If not expired and not admin, redirect to start
    if not quiz.is_expired() and not request.user.is_staff:
        return redirect('start_quiz', quiz_id=quiz_id)
    questions = quiz.questions.all().order_by('order')
    context = {
        'quiz': quiz,
        'questions': questions,
    }
    return render(request, 'expired_quiz_answers.html', context)


def quiz_result(request, attempt_id):
    attempt = get_object_or_404(StudentAttempt, id=attempt_id)
    if not attempt.is_submitted:
        return redirect('take_quiz', quiz_id=attempt.quiz.id)
    answers = attempt.answers.all().select_related('question', 'selected_option')
    questions_with_answers = []
    for question in attempt.quiz.questions.all():
        try:
            answer = answers.get(question=question)
            questions_with_answers.append({
                'question': question,
                'student_answer': answer,
                'correct_option': question.options.filter(is_correct=True).first(),
                'is_correct': answer.selected_option.is_correct,
            })
        except StudentAnswer.DoesNotExist:
            questions_with_answers.append({
                'question': question,
                'student_answer': None,
                'correct_option': question.options.filter(is_correct=True).first(),
                'is_correct': False,
            })
    percentage = (attempt.score / attempt.total_questions * 100) if attempt.total_questions > 0 else 0
    
    # Check if any warnings exist for this attempt
    has_warning = attempt.tab_switch_count > 0 or attempt.is_disqualified

    context = {
        'attempt': attempt,
        'questions_with_answers': questions_with_answers,
        'percentage': percentage,
        'has_warning': has_warning,
    }
    for key in ['attempt_id', 'session_id']:
        if key in request.session:
            del request.session[key]
    return render(request, 'quiz_result.html', context)

# ==================== এই functions গুলো views.py তে ADD করো (শেষে paste করো) ====================

# views.py এর একদম শেষে এই code টা add করো:

def leaderboard(request):
    if not request.user.is_authenticated:
        return redirect('student_login')

    quizzes = Quiz.objects.filter(is_published=True).order_by('-created_at')
    selected_quiz_id = request.GET.get('quiz_id')
    selected_quiz = None
    leaderboard_data = []

    if selected_quiz_id:
        selected_quiz = get_object_or_404(Quiz, id=selected_quiz_id)
        # Fetch all registered students
        students = User.objects.filter(student_profile__isnull=False, is_staff=False, is_superuser=False).select_related('student_profile')
        
        # Fetch all submitted attempts for this quiz in bulk to avoid N+1 query problem
        attempts = StudentAttempt.objects.filter(quiz=selected_quiz, is_submitted=True)
        best_attempts_by_student = {}
        for a in attempts:
            if a.student_id:
                current_best = best_attempts_by_student.get(a.student_id)
                if not current_best or a.score > current_best.score or (a.score == current_best.score and a.submitted_at < current_best.submitted_at):
                    best_attempts_by_student[a.student_id] = a

        temp_data = []
        for student in students:
            best_attempt = best_attempts_by_student.get(student.id)
            
            score = best_attempt.score if best_attempt else 0
            percentage = (score / best_attempt.total_questions * 100) if (best_attempt and best_attempt.total_questions > 0) else 0
            
            temp_data.append({
                'student': student,
                'profile': student.student_profile,
                'score': score,
                'total_score': score, # For template consistency
                'percentage': round(percentage, 1),
                'attempt': best_attempt,
            })
        
        # Rank by score desc
        temp_data.sort(key=lambda x: -x['score'])
        for rank, item in enumerate(temp_data, start=1):
            item['rank'] = rank
            leaderboard_data.append(item)

    else:
        # All students combined — even those with no activity yet
        # Uses the unified scoring system: (Attendance*5) + Best Quiz Marks + Assignment Marks
        students = User.objects.filter(student_profile__isnull=False, is_staff=False, is_superuser=False).select_related('student_profile')
        all_scores = get_all_student_scores()

        temp = []
        for student in students:
            sc = all_scores.get(student.id, {'quiz_score': 0, 'att_score': 0, 'ass_score': 0, 'total': 0, 'quiz_count': 0})
            profile = student.student_profile
            temp.append({
                'student': student,
                'profile': profile,
                'total_score': sc['total'],
                'quiz_score': sc['quiz_score'],
                'attendance_score': sc['att_score'],
                'assignment_score': sc['ass_score'],
                'quiz_count': sc['quiz_count'],
            })

        temp.sort(key=lambda x: -x['total_score'])
        for rank, item in enumerate(temp, start=1):
            item['rank'] = rank
            leaderboard_data.append(item)

    context = {
        'quizzes': quizzes,
        'selected_quiz': selected_quiz,
        'top_three': leaderboard_data[:3],
        'remaining_students': leaderboard_data[3:],
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        from django.template.loader import render_to_string
        html_podium = render_to_string('leaderboard_podium_partial.html', context, request=request)
        html_table = render_to_string('leaderboard_table_partial.html', context, request=request)
        return JsonResponse({
            'success': True,
            'html_podium': html_podium,
            'html_table': html_table,
            'quiz_title': selected_quiz.title if selected_quiz else "Overall Rankings"
        })

    return render(request, 'leaderboard.html', context)


@login_required(login_url='admin_login')
def adjust_score(request, attempt_id):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    attempt = get_object_or_404(StudentAttempt, id=attempt_id)

    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            action = data.get('action')
            amount = int(data.get('amount', 1))

            if action == 'add':
                attempt.score = min(attempt.score + amount, attempt.total_questions)
            elif action == 'minus':
                attempt.score = max(attempt.score - amount, 0)
            elif action == 'set':
                attempt.score = max(0, min(amount, attempt.total_questions))

            attempt.save()
            return JsonResponse({
                'success': True,
                'new_score': attempt.score,
                'total': attempt.total_questions,
                'percentage': round((attempt.score / attempt.total_questions * 100) if attempt.total_questions > 0 else 0, 1)
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False}, status=400)


# ==================== NEW LMS VIEWS ====================

@login_required(login_url='student_login')
def student_dashboard(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    
    # Quiz stats
    attempts = StudentAttempt.objects.filter(student=request.user, is_submitted=True).order_by('-submitted_at')
    total_quiz_score = sum(a.score for a in attempts)
    recent_attempt = attempts.first()
    recent_quiz_score = recent_attempt.score if recent_attempt else None
    recent_quiz_total = recent_attempt.total_questions if recent_attempt else None
    
    # Assignment stats (Improved Logic)
    now = timezone.now()
    all_assignments = Assignment.objects.all()
    ass_status = {'completed': 0, 'pending': 0, 'expired': 0}
    for a in all_assignments:
        submission = AssignmentSubmission.objects.filter(student=request.user, assignment=a).first()
        if submission:
            ass_status['completed'] += 1
        elif a.is_deadline_passed:
            ass_status['expired'] += 1
        else:
            ass_status['pending'] += 1

    # Unified Recent Score (Quiz or Assignment)
    recent_quiz = StudentAttempt.objects.filter(student=request.user, is_submitted=True).order_by('-submitted_at').first()
    recent_ass = AssignmentSubmission.objects.filter(student=request.user, is_graded=True, is_published=True).order_by('-submitted_at').first()
    
    recent_score_data = None
    if recent_quiz and recent_ass:
        if recent_quiz.submitted_at > recent_ass.submitted_at:
            recent_score_data = {'score': recent_quiz.score, 'total': recent_quiz.total_questions, 'type': 'Quiz', 'title': recent_quiz.quiz.title}
        else:
            recent_score_data = {'score': recent_ass.marks, 'total': recent_ass.assignment.total_marks, 'type': 'Assignment', 'title': recent_ass.assignment.title}
    elif recent_quiz:
        recent_score_data = {'score': recent_quiz.score, 'total': recent_quiz.total_questions, 'type': 'Quiz', 'title': recent_quiz.quiz.title}
    elif recent_ass:
        recent_score_data = {'score': recent_ass.marks, 'total': recent_ass.assignment.total_marks, 'type': 'Assignment', 'title': recent_ass.assignment.title}
    
    # --- Unified Ranking System (Matches Leaderboard) ---
    all_scores = get_all_student_scores()
    rank_list = [{'student_id': sid, 'total_score': info['total']} for sid, info in all_scores.items()]
    rank_list.sort(key=lambda x: -x['total_score'])
    my_rank = next((i for i, x in enumerate(rank_list, 1) if x['student_id'] == request.user.id), None)
    
    # --- Unified Raw Mark Scoring System ---
    # Formula: Total = (Attendance * 5) + Quiz Marks + Assignment Marks
    
    # --- Use centralized scoring helper ---
    my_scores = all_scores.get(request.user.id, {'quiz_score': 0, 'ass_score': 0, 'att_score': 0, 'total': 0})
    student_q_earned = my_scores['quiz_score']
    student_a_earned = my_scores['ass_score']
    attendance_earned = my_scores['att_score']

    all_quizzes = Quiz.objects.filter(is_published=True)
    total_q_possible = sum(q.questions.count() for q in all_quizzes)
    all_assignments = Assignment.objects.all()
    total_a_possible = sum(a.total_marks for a in all_assignments)

    attendance_p = min(round((profile.attendance_count / 30) * 100), 100)
    quiz_p = round((student_q_earned / total_q_possible * 100)) if total_q_possible > 0 else 0
    assignment_p = round((student_a_earned / total_a_possible * 100)) if total_a_possible > 0 else 0

    # New Features Data
    now = timezone.now()
    upcoming_quizzes = Quiz.objects.filter(is_published=True, start_time__gt=now).order_by('start_time')
    recent_activities = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')[:50] 
    latest_notices = Notice.objects.all().order_by('-created_at')[:20] # Get more for see more toggle

    # Calculate total tab switches across all quizzes (from WarningLog for accuracy)
    total_tab_switches = WarningLog.objects.filter(attempt__student=request.user).count()

    context = {
        'profile': profile,
        'total_quiz_score': student_q_earned,
        'student_q_earned': student_q_earned,  # Matches template expectation
        'recent_score_data': recent_score_data,
        'ass_status': ass_status,
        'rank': my_rank,
        'attendance_p': attendance_p,
        'quiz_p': quiz_p,
        'assignment_p': assignment_p,
        'total_q_possible': total_q_possible,
        'student_a_earned': student_a_earned,
        'student_a_earned_val': student_a_earned,
        'total_a_possible': total_a_possible,
        'total_quizzes': Quiz.objects.filter(is_published=True).count(),
        'upcoming_quizzes': upcoming_quizzes,
        'recent_activities': recent_activities,
        'latest_notices': latest_notices,
        'total_students_count': User.objects.filter(student_profile__isnull=False).exclude(is_staff=True).count(),
        'overall_total_marks': my_scores['total'],
        'total_tab_switches': total_tab_switches,
    }
    return render(request, 'dashboard.html', context)


@login_required
def assignment_list(request):
    assignments = Assignment.objects.all().order_by('-created_at')
    
    # If student, get their submission data
    if not request.user.is_staff:
        submissions = AssignmentSubmission.objects.filter(student=request.user).values_list('assignment_id', flat=True)
        submitted_count = submissions.count()
        assignment_data = []
        for a in assignments:
            assignment_data.append({
                'assignment': a,
                'is_submitted': a.id in submissions,
                'submission': AssignmentSubmission.objects.filter(student=request.user, assignment=a).first() if a.id in submissions else None
            })
    else:
        # Admin: Show total assignments and submissions for the LATEST active assignment
        assignment_data = [{'assignment': a} for a in assignments]
        latest = assignments.first()
        if latest:
            submitted_count = AssignmentSubmission.objects.filter(assignment=latest).count()
        else:
            submitted_count = 0
        
    return render(request, 'assignment_list.html', {
        'assignments': assignment_data,
        'submitted_count': submitted_count
    })


@login_required(login_url='admin_login')
def edit_assignment(request, assignment_id):
    if not request.user.is_staff:
        return redirect('home')
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    if request.method == 'POST':
        assignment.title = request.POST.get('title')
        assignment.description = request.POST.get('description')
        assignment.total_marks = request.POST.get('total_marks', 100)
        
        deadline = request.POST.get('deadline')
        if not deadline:
            messages.error(request, "Deadline is required.")
            return render(request, 'edit_assignment.html', {'assignment': assignment})
            
        assignment.deadline = deadline
        
        if request.FILES.get('requirements_file'):
            assignment.requirements_file = request.FILES['requirements_file']
            
        assignment.save()
        messages.success(request, f"Assignment '{assignment.title}' updated successfully!")
        return redirect('assignment_list')
        
    return render(request, 'edit_assignment.html', {'assignment': assignment})


@login_required(login_url='admin_login')
def delete_assignment(request, assignment_id):
    if not request.user.is_staff:
        return JsonResponse({'success': False}, status=403)
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == 'POST':
        assignment.delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}, status=400)


@login_required(login_url='student_login')
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submission = AssignmentSubmission.objects.filter(student=request.user, assignment=assignment).first()
    return render(request, 'assignment_detail.html', {'assignment': assignment, 'submission': submission})


@login_required(login_url='student_login')
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # NEW: Check if deadline passed
    if assignment.is_deadline_passed:
        messages.error(request, "The deadline for this assignment has passed. Submissions are no longer accepted.")
        return redirect('assignment_detail', assignment_id=assignment_id)

    if request.method == 'POST':
        file = request.FILES.get('assignment_file')
        drive_link = request.POST.get('drive_link')
        
        if not file and not drive_link:
            messages.error(request, "Please upload a file or provide a Google Drive link.")
            return redirect('assignment_detail', assignment_id=assignment_id)
            
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ['.zip', '.pdf', '.jpg', '.jpeg', '.png']:
                messages.error(request, "Invalid file type. Please upload a ZIP, PDF, or Image.")
                return redirect('assignment_detail', assignment_id=assignment_id)
            
        if AssignmentSubmission.objects.filter(student=request.user, assignment=assignment).exists():
            messages.warning(request, f"You have already submitted this assignment.")
            return redirect('assignment_detail', assignment_id=assignment_id)

        AssignmentSubmission.objects.create(
            student=request.user,
            assignment=assignment,
            file=file,
            drive_link=drive_link,
            submitted_at=timezone.now()
        )
        log_activity(request.user, "Submitted Assignment", f"Submitted solution for: {assignment.title}")
        messages.success(request, f"Assignment '{assignment.title}' submitted successfully!")
        return redirect('assignment_detail', assignment_id=assignment.id)
    return redirect('assignment_detail', assignment_id=assignment_id)


@login_required(login_url='admin_login')
def add_assignment(request):
    if not request.user.is_staff:
        return redirect('home')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        total_marks = request.POST.get('total_marks', 100)
        deadline = request.POST.get('deadline')
        req_file = request.FILES.get('requirements_file')
        
        if not deadline:
            messages.error(request, "Deadline is required.")
            return render(request, 'add_assignment.html')
            
        new_assignment = Assignment.objects.create(
            title=title,
            description=description,
            total_marks=total_marks,
            deadline=deadline,
            requirements_file=req_file
        )
        messages.success(request, f"Assignment '{title}' created successfully!")
        return redirect('assignment_list')
        
    return render(request, 'add_assignment.html')


@login_required(login_url='student_login')
def notice_list(request):
    from django.db.models import Q
    notices_qs = Notice.objects.filter(
        Q(recipient__isnull=True) | Q(recipient=request.user),
        is_active=True,
        publish_at__lte=timezone.now()
    ).order_by('-publish_at')
    
    notices = list(notices_qs)
    
    import re
    quiz_pattern = re.compile(r'/quiz/(\d+)/')
    for notice in notices:
        if notice.link:
            match = quiz_pattern.search(notice.link)
            if match:
                quiz_id = int(match.group(1))
                try:
                    from quiz_app.models import Quiz
                    quiz = Quiz.objects.get(id=quiz_id)
                    if quiz.is_expired():
                        notice.is_quiz_expired = True
                except Quiz.DoesNotExist:
                    pass
    
    unread_ids = []
    if not request.user.is_staff:
        # Find which ones were unread before we mark them
        read_ids = set(ReadNotice.objects.filter(user=request.user).values_list('notice_id', flat=True))
        for notice in notices:
            if notice.id not in read_ids:
                unread_ids.append(notice.id)
                ReadNotice.objects.get_or_create(user=request.user, notice=notice)
            
    return render(request, 'notices.html', {
        'notices': notices,
        'unread_ids': unread_ids
    })

@require_http_methods(["POST"])
@csrf_exempt
def mark_notices_read(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    try:
        # We don't even need to parse body if we just want to mark all
        active_notices = Notice.objects.filter(is_active=True)
        read_notices = [ReadNotice(user=request.user, notice=notice) for notice in active_notices]
        ReadNotice.objects.bulk_create(read_notices, ignore_conflicts=True)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='student_login')
def resource_list(request):
    # Group resources by date
    resources = Resource.objects.all().order_by('-resource_date', '-created_at')
    
    from collections import OrderedDict
    grouped_resources = OrderedDict()
    
    for r in resources:
        date_obj = r.resource_date
        if date_obj not in grouped_resources:
            grouped_resources[date_obj] = []
        grouped_resources[date_obj].append(r)
        
    return render(request, 'resources.html', {'grouped_resources': grouped_resources})

@login_required(login_url='admin_login')
def add_resource(request):
    if not request.user.is_staff:
        return redirect('home')
        
    if request.method == 'POST':
        title_prefix = request.POST.get('title', 'Resource')
        category = request.POST.get('category')
        description = request.POST.get('description', '')
        video_url = request.POST.get('video_url', '')
        
        # Ensure resource_date is a date object for consistent grouping
        resource_date_str = request.POST.get('resource_date')
        if resource_date_str:
            try:
                from datetime import datetime
                resource_date = datetime.strptime(resource_date_str, '%Y-%m-%d').date()
            except:
                resource_date = timezone.now().date()
        else:
            resource_date = timezone.now().date()
            
        files = request.FILES.getlist('files')
        success_count = 0
        
        # 1. Handle Video URL
        if video_url:
            try:
                Resource.objects.create(
                    title=title_prefix,
                    category=category,
                    description=description,
                    video_url=video_url,
                    resource_date=resource_date
                )
                success_count += 1
            except Exception as e:
                messages.error(request, f"Error adding video: {str(e)}")
        
        # 2. Handle Files
        if files:
            for f in files:
                try:
                    if category == 'code':
                        title = f.name
                    else:
                        title = f"{title_prefix} - {f.name}" if (len(files) > 1 or video_url) else title_prefix
                    Resource.objects.create(
                        title=title,
                        category=category,
                        description=description,
                        file=f,
                        resource_date=resource_date
                    )
                    success_count += 1
                except Exception as e:
                    messages.error(request, f"Error adding file {f.name}: {str(e)}")
        
        if success_count > 0:
            messages.success(request, f"Successfully added {success_count} items for {resource_date.strftime('%d/%m/%Y')}!")
        
        return redirect('resource_list')
        
    return redirect('resource_list')

@login_required(login_url='admin_login')
def delete_resource(request, resource_id):
    if not request.user.is_staff:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        return redirect('home')
        
    resource = get_object_or_404(Resource, id=resource_id)
    title = resource.title
    resource.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f"Resource '{title}' deleted successfully!"})
        
    messages.success(request, f"Resource '{title}' deleted successfully!")
    return redirect('resource_list')

@login_required(login_url='admin_login')
def delete_session(request):
    if not request.user.is_staff:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        return redirect('home')
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        if date_str:
            Resource.objects.filter(resource_date=date_str).delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f"All resources for {date_str} have been deleted."})
            messages.success(request, f"Session for {date_str} deleted.")
    return redirect('resource_list')

@login_required(login_url='student_login')
def teacher_list(request):
    # Ensure the 3 specific admins exist as Teachers
    admins_to_ensure = [
        {'username': 'admin_refat', 'name': 'MD Refat', 'email': 'rifat732151@gmail.com', 'designation': 'Lecturer', 'phone': '01234567890', 'hours': 'Mon, Wed (10:00 AM - 12:00 PM)'},
        {'username': 'admin_ridoy', 'name': 'Hasin Hasnat', 'email': 'rsridoykhan000@gmail.com', 'designation': 'Lecturer', 'phone': '01787026652', 'hours': 'Tue, Thu (02:00 PM - 04:00 PM)'},
        {'username': 'admin_rafi', 'name': 'Ridwanol Haque Rafi', 'email': 'rafiqul.h@university.edu', 'designation': 'System Administrator', 'phone': '01987654321', 'hours': 'Sun, Tue (11:00 AM - 01:00 PM)'},
    ]
    
    for admin_data in admins_to_ensure:
        u = User.objects.filter(username=admin_data['username']).first()
        if u:
            t, created = Teacher.objects.get_or_create(user=u)
            if created:
                t.name = admin_data['name']
                t.email = admin_data['email']
                t.designation = admin_data['designation']
                t.phone = admin_data['phone']
                t.office_hours = admin_data['hours']
                t.department = 'Computer Science and Technology'
                t.save()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        teachers = Teacher.objects.filter(
            Q(name__icontains=search_query) |
            Q(designation__icontains=search_query) |
            Q(department__icontains=search_query)
        ).select_related('user', 'user__student_profile').order_by('id')
    else:
        teachers = Teacher.objects.all().select_related('user', 'user__student_profile').order_by('id')
    
    return render(request, 'teacher_list.html', {'teachers': teachers, 'search_query': search_query})




# Admin Grade Submission
@login_required(login_url='admin_login')
def admin_submissions(request):
    if not request.user.is_staff:
        return redirect('home')
    
    assignment_id = request.GET.get('assignment')
    if assignment_id:
        submissions = AssignmentSubmission.objects.filter(assignment_id=assignment_id).select_related('student', 'assignment').order_by('-submitted_at')
        has_graded_unpublished = AssignmentSubmission.objects.filter(assignment_id=assignment_id, is_graded=True, is_published=False).exists()
        has_published = AssignmentSubmission.objects.filter(assignment_id=assignment_id, is_published=True).exists()
    else:
        submissions = AssignmentSubmission.objects.all().select_related('student', 'assignment').order_by('-submitted_at')
        has_graded_unpublished = AssignmentSubmission.objects.filter(is_graded=True, is_published=False).exists()
        has_published = AssignmentSubmission.objects.filter(is_published=True).exists()
        
    return render(request, 'admin_submissions.html', {
        'submissions': submissions,
        'assignment_id': assignment_id,
        'has_graded_unpublished': has_graded_unpublished,
        'has_published': has_published
    })


@login_required(login_url='admin_login')
def grade_submission(request, submission_id):
    if not request.user.is_staff:
        return JsonResponse({'success': False}, status=403)
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    if request.method == 'POST':
        submission.marks = int(request.POST.get('marks', 0))
        submission.feedback = request.POST.get('feedback', '')
        submission.is_graded = True
        submission.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('ajax') == 'true':
            return JsonResponse({'success': True, 'message': f"Marks saved for {submission.student.get_full_name()}"})
            
        messages.success(request, f"Marks saved for {submission.student.get_full_name()}. You can now publish it.")
        return redirect('admin_submissions')
    return JsonResponse({'success': False})

@login_required(login_url='admin_login')
def publish_assignment_result(request, submission_id):
    if not request.user.is_staff:
        return redirect('home')
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    if not submission.is_graded:
        messages.error(request, "Please grade the assignment first.")
        return redirect('admin_submissions')
    
    submission.is_published = True
    submission.save()
    
    # Auto-notice: Assignment result published manually
    Notice.objects.create(
        title=f"📊 Result Published: {submission.assignment.title}",
        content=f"Your result for assignment '{submission.assignment.title}' has been published. Marks obtained: {submission.marks}/{submission.assignment.total_marks}. Check your profile for details.",
        recipient=submission.student
    )
    messages.success(request, f"Result published for {submission.student.get_full_name()}!")
    return redirect(f"{reverse('admin_submissions')}?assignment={submission.assignment.id}")


@login_required(login_url='admin_login')
def cancel_grade(request, submission_id):
    if not request.user.is_staff:
        return redirect('home')
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    
    submission.is_graded = False
    submission.is_published = False
    submission.marks = 0
    submission.feedback = ""
    submission.save()
    
    # Delete notice if any existed for this result
    Notice.objects.filter(
        recipient=submission.student,
        title=f"📊 Result Published: {submission.assignment.title}"
    ).delete()
    
    messages.success(request, f"Grading reset to pending for {submission.student.get_full_name()}!")
    
    redirect_url = reverse('admin_submissions')
    assignment_id = request.GET.get('assignment')
    if assignment_id:
        redirect_url += f"?assignment={assignment_id}"
    return redirect(redirect_url)


@login_required(login_url='admin_login')
def publish_all_submissions(request):
    if not request.user.is_staff:
        return redirect('home')
    
    assignment_id = request.GET.get('assignment')
    if assignment_id:
        submissions = AssignmentSubmission.objects.filter(assignment_id=assignment_id, is_graded=True, is_published=False)
    else:
        submissions = AssignmentSubmission.objects.filter(is_graded=True, is_published=False)
        
    count = 0
    for submission in submissions:
        submission.is_published = True
        submission.save()
        
        # Create notice for the student
        Notice.objects.get_or_create(
            title=f"📊 Result Published: {submission.assignment.title}",
            recipient=submission.student,
            defaults={
                'content': f"Your result for assignment '{submission.assignment.title}' has been published. Marks obtained: {submission.marks}/{submission.assignment.total_marks}. Check your profile for details."
            }
        )
        count += 1
        
    if count > 0:
        messages.success(request, f"Successfully published results for {count} student(s)!")
    else:
        messages.info(request, "No new graded results to publish.")
        
    redirect_url = reverse('admin_submissions')
    if assignment_id:
        redirect_url += f"?assignment={assignment_id}"
    return redirect(redirect_url)


@login_required(login_url='admin_login')
def unpublish_all_submissions(request):
    if not request.user.is_staff:
        return redirect('home')
        
    assignment_id = request.GET.get('assignment')
    if assignment_id:
        submissions = AssignmentSubmission.objects.filter(assignment_id=assignment_id, is_published=True)
    else:
        submissions = AssignmentSubmission.objects.filter(is_published=True)
        
    count = 0
    for submission in submissions:
        submission.is_published = False
        submission.save()
        
        # Delete notice for the student
        Notice.objects.filter(
            recipient=submission.student,
            title=f"📊 Result Published: {submission.assignment.title}"
        ).delete()
        count += 1
        
    if count > 0:
        messages.success(request, f"Successfully unpublished results for {count} student(s)!")
    else:
        messages.info(request, "No published results found to unpublish.")
        
    redirect_url = reverse('admin_submissions')
    if assignment_id:
        redirect_url += f"?assignment={assignment_id}"
    return redirect(redirect_url)


@login_required(login_url='admin_login')
def add_notice(request):
    if not request.user.is_staff:
        return redirect('home')
    if request.method == 'POST':
        notice = Notice.objects.create(
            title=request.POST.get('title'),
            content=request.POST.get('content')
        )
        for f in request.FILES.getlist('attachments'):
            NoticeAttachment.objects.create(notice=notice, file=f)
        return redirect('notice_list')
    return render(request, 'add_notice.html')

@login_required(login_url='admin_login')
def delete_notice(request, notice_id):
    if not request.user.is_staff:
        return redirect('home')
    
    notice = get_object_or_404(Notice, id=notice_id)
    notice.delete()
    return redirect('notice_list')

@login_required(login_url='admin_login')
def delete_all_notices(request):
    if not request.user.is_staff:
        return redirect('home')
    Notice.objects.all().delete()
    messages.success(request, "All announcements have been deleted.")
    return redirect('notice_list')


@login_required(login_url='student_login')
def admin_student_progress(request, user_id):
    if not request.user.is_staff:
        return redirect('home')
    
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = StudentProfile.objects.get_or_create(user=target_user)
    
    # --- Unified Ranking System (Matches Leaderboard) ---
    all_scores = get_all_student_scores()
    rank_list = [{'student_id': sid, 'total_score': info['total']} for sid, info in all_scores.items()]
    rank_list.sort(key=lambda x: -x['total_score'])
    my_rank = next((i for i, x in enumerate(rank_list, 1) if x['student_id'] == target_user.id), None)

    # Detailed Data
    attempts = StudentAttempt.objects.filter(student=target_user, is_submitted=True).order_by('-submitted_at')
    submissions = AssignmentSubmission.objects.filter(student=target_user).select_related('assignment').order_by('-submitted_at')
    
    # Calculate Total Points for this student (using the rank_list already calculated above)
    student_total_score = next((x['total_score'] for x in rank_list if x['student_id'] == target_user.id), 0)

    # Activity Data
    recent_activities = ActivityLog.objects.filter(user=target_user).order_by('-timestamp')[:50]

    # Tab Switches (Total from all warnings)
    total_tab_switches = WarningLog.objects.filter(attempt__student=target_user).count()

    # Stats for Academic Overview — use centralized helper
    target_sc = all_scores.get(target_user.id, {'quiz_score': 0, 'ass_score': 0, 'att_score': 0, 'total': 0})
    student_q_earned = target_sc['quiz_score']
    student_a_earned = target_sc['ass_score']

    all_quizzes = Quiz.objects.filter(is_published=True)
    total_q_possible = sum(q.questions.count() for q in all_quizzes)
    all_assignments = Assignment.objects.all()
    total_a_possible = sum(a.total_marks for a in all_assignments)

    attendance_p = min(round((profile.attendance_count / 30) * 100), 100)
    quiz_p = round((student_q_earned / total_q_possible * 100)) if total_q_possible > 0 else 0
    assignment_p = round((student_a_earned / total_a_possible * 100)) if total_a_possible > 0 else 0

    context = {
        'target_user': target_user,
        'profile': profile,
        'attempts': attempts,
        'submissions': submissions,
        'recent_activities': recent_activities,
        'my_rank': my_rank,
        'total_marks': student_total_score,
        'total_tab_switches': total_tab_switches,
        'quiz_p': quiz_p,
        'student_q_earned': student_q_earned,
        'total_q_possible': total_q_possible,
        'attendance_p': attendance_p,
        'assignment_p': assignment_p,
        'student_a_earned': student_a_earned,
        'total_a_possible': total_a_possible,
    }
    return render(request, 'admin_student_progress.html', context)


@login_required(login_url='admin_login')
def admin_adjust_bonus_marks(request, user_id):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        profile, _ = StudentProfile.objects.get_or_create(user=target_user)
        
        try:
            import json
            data = json.loads(request.body)
            action = data.get('action')
            amount_val = data.get('amount', 0)
            category = data.get('category', 'overall')
            
            # Ensure amount is an integer
            amount = int(amount_val) if amount_val else 0
            
            # Map category to field
            field_map = {
                'overall': 'bonus_marks',
                'quiz': 'quiz_bonus_marks',
                'assignment': 'assignment_bonus_marks',
                'attendance': 'attendance_bonus_marks'
            }
            field_name = field_map.get(category, 'bonus_marks')
            
            current_val = getattr(profile, field_name)
            if action == 'add':
                setattr(profile, field_name, current_val + amount)
            elif action == 'minus':
                setattr(profile, field_name, current_val - amount)

            
            profile.save()
            return JsonResponse({
                'success': True, 
                'new_bonus': profile.bonus_marks,
                'message': f'Bonus marks updated to {profile.bonus_marks}'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


@login_required
def student_list(request):
    search_query = request.GET.get('search', '')
    base_qs = StudentProfile.objects.filter(user__is_staff=False, user__is_superuser=False).select_related('user')
    if search_query:
        students_qs = base_qs.filter(
            Q(user__first_name__icontains=search_query) | 
            Q(user__last_name__icontains=search_query) |
            Q(student_id__icontains=search_query) |
            Q(user__username__icontains=search_query)
        ).order_by('student_id')
    else:
        students_qs = base_qs.order_by('student_id')
    
    # Convert to list to reorder
    students_list = list(students_qs)
    
    # Move current user to top if they exist in the list
    try:
        user_profile = request.user.student_profile
        if user_profile in students_list:
            students_list.remove(user_profile)
            students_list.insert(0, user_profile)
    except Exception:
        pass

    return render(request, 'student_list.html', {'students': students_list, 'search_query': search_query})


@login_required(login_url='admin_login')
def delete_student(request, user_id):
    if not request.user.is_staff:
        return redirect('student_login')
    
    student_user = get_object_or_404(User, id=user_id, is_staff=False, is_superuser=False)
    
    if request.method == 'POST':
        student_user.delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


@login_required
def admin_reports(request):
    if not request.user.is_staff:
        return redirect('home')
    
    from .utils import generate_submission_report
    
    # Handle direct generation request
    gen_type = request.GET.get('generate_type')
    gen_id = request.GET.get('generate_id')
    
    if gen_type and gen_id:
        try:
            report = generate_submission_report(gen_type, gen_id)
            if report:
                messages.success(request, f"Successfully generated {gen_type} report.")
            else:
                messages.warning(request, f"Could not generate report. No submissions found for this {gen_type}.")
        except Exception as e:
            messages.error(request, f"Error generating report: {str(e)}")
            
        return redirect('admin_reports')
            
    # Fetch all quizzes and assignments
    quizzes = Quiz.objects.all().order_by('-created_at')
    assignments = Assignment.objects.all().order_by('-created_at')
    
    # Map existing reports
    quiz_reports = {r.quiz_id: r for r in SessionReport.objects.filter(report_type='quiz')}
    assignment_reports = {r.assignment_id: r for r in SessionReport.objects.filter(report_type='assignment')}
    
    context = {
        'quizzes': quizzes,
        'assignments': assignments,
        'quiz_reports': quiz_reports,
        'assignment_reports': assignment_reports,
    }
    return render(request, 'admin_reports.html', context)
@login_required(login_url='admin_login')
def attendance_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')
    
    date_str = request.GET.get('date')
    if date_str:
        try:
            date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            date = timezone.now().date()
    else:
        date = timezone.now().date()

    students = StudentProfile.objects.exclude(user__is_staff=True).select_related('user').order_by('student_id')
    attendance_records = Attendance.objects.filter(date=date)
    attendance_map = {record.student_id: record.status for record in attendance_records}
    
    return render(request, 'attendance.html', {
        'students': students,
        'date': date,
        'attendance_map': attendance_map,
    })

@login_required(login_url='admin_login')
@require_http_methods(['POST'])
def mark_attendance(request):
    if not request.user.is_staff:
        return redirect('home')

    date_str = request.POST.get('date')
    date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    
    students = StudentProfile.objects.all()
    for student in students:
        status = request.POST.get(f'status_{student.id}')
        if status:
            Attendance.objects.update_or_create(
                student=student,
                date=date,
                defaults={'status': status}
            )

    
    messages.success(request, f'Attendance for {date} updated successfully!')
    from django.urls import reverse
    return redirect(f"{reverse('attendance_dashboard')}?date={date_str}")

@login_required(login_url='admin_login')
def attendance_report(request):
    if not request.user.is_staff:
        return redirect('home')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    report_data = []

    if start_date == 'None': start_date = None
    if end_date == 'None': end_date = None

    start_display = start_date
    end_display = end_date

    if start_date:
        if not end_date:
            end_date = start_date
        
        try:
            from datetime import datetime
            start_display = datetime.strptime(start_date, '%Y-%m-%d').strftime('%d/%m/%Y')
            end_display = datetime.strptime(end_date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            pass

        from datetime import datetime, timedelta
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            total_days_in_range = (end_dt - start_dt).days + 1
        except Exception:
            total_days_in_range = None

        students = StudentProfile.objects.filter(user__is_staff=False).select_related('user').order_by('student_id')
        for student in students:
            attendances = Attendance.objects.filter(student=student, date__range=[start_date, end_date])
            present_count = attendances.filter(status='Present').count()
            recorded_count = attendances.count()

            # Total days = actual calendar days in range
            total = total_days_in_range if total_days_in_range else recorded_count
            absent_count = total - present_count

            report_data.append({
                'student': student,
                'present': present_count,
                'absent': absent_count if absent_count >= 0 else 0,
                'total': total
            })

    return render(request, 'attendance_report.html', {
        'report_data': report_data,
        'start_date': start_date,
        'end_date': end_date,
        'start_display': start_display,
        'end_display': end_display
    })


from django.http import FileResponse, Http404

def view_resource_file(request, resource_id):
    try:
        resource = Resource.objects.get(id=resource_id)
        if not resource.file:
            raise Http404("No file associated with this resource")
            
        # Check if we are using remote storage (like Cloudinary)
        if os.environ.get('VERCEL') or not settings.DEBUG:
            return redirect(resource.file.url)
            
        file_path = resource.file.path
        if not os.path.exists(file_path):
             raise Http404("File does not exist on server")
             
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        # Ensure it's displayed inline
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except Resource.DoesNotExist:
        raise Http404("Resource not found")


import sys
import traceback
from django.http import HttpResponseBadRequest

def custom_bad_request_handler(request, exception=None):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = ""
    if exc_value:
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    else:
        tb_str = f"No exception traceback available. Exception: {exception}"

    return HttpResponseBadRequest(
        f"Custom 400 Bad Request Diagnostic Page\n\n"
        f"Exception: {exception}\n\n"
        f"Traceback:\n{tb_str}",
        content_type="text/plain"
    )

