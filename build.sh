#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py makemigrations
python manage.py migrate
python manage.py shell -c "
from smsapp.models import Student
from django.contrib.auth import get_user_model
import os

User = get_user_model()

# Create admin user if it doesn't exist
admin, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@example.com',
        'is_staff': True,
        'is_superuser': True
    }
)

# Set password whether user existed or was just created
admin.set_password(os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123'))
admin.save()

if created:
    print('Admin user created and password set')
else:
    print('Admin user already exists, password updated')

# Generate dummy data if needed
if Student.objects.count() == 0:
    # Add your dummy data generation code here
    print('Dummy data generated')
else:
    print('Data already exists, skipping')
"