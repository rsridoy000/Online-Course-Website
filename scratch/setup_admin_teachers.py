import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')
django.setup()

from django.contrib.auth.models import User
from quiz_app.models import Teacher

def create_admin_teachers():
    admins = [
        {
            'username': 'admin_refat',
            'name': 'MD Refat',
            'email': 'rifat732151@gmail.com',
            'designation': 'Lecturer',
            'phone': '01234567890',
            'hours': 'Mon, Wed (10:00 AM - 12:00 PM)'
        },
        {
            'username': 'admin_ridoy',
            'name': 'Hasin Hasnat',
            'email': 'rsridoykhan000@gmail.com',
            'designation': 'Lecturer',
            'phone': '01787026652',
            'hours': 'Tue, Thu (02:00 PM - 04:00 PM)'
        },
        {
            'username': 'admin_rafi',
            'name': 'Ridwanol Haque Rafi',
            'email': 'rafiqul.h@university.edu',
            'designation': 'System Administrator',
            'phone': '01987654321',
            'hours': 'Sun, Tue (11:00 AM - 01:00 PM)'
        }
    ]

    for data in admins:
        user, created = User.objects.get_or_create(username=data['username'])
        if created:
            user.set_password('730323')
            user.is_staff = True
            user.is_superuser = True
            user.save()
        
        # Split name for first/last
        parts = data['name'].split()
        user.first_name = parts[0]
        user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        user.save()

        teacher, _ = Teacher.objects.get_or_create(user=user)
        teacher.name = data['name']
        teacher.email = data['email']
        teacher.designation = data['designation']
        teacher.phone = data['phone']
        teacher.office_hours = data['hours']
        teacher.department = 'Computer Science and Technology'
        teacher.save()
        print(f"Updated teacher: {data['name']}")

if __name__ == "__main__":
    create_admin_teachers()
