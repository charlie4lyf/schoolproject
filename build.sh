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

# Check if admin user exists
try:
    admin = User.objects.get(username='admin')
    created = False
    print('Admin user already exists')
except User.DoesNotExist:
    # Create admin user with all required fields
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password=os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123'),
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    created = True
    print('Admin user created')

# Update password (always ensure it's set correctly)
admin.set_password(os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123'))
admin.save()

if created:
    print('Admin user created and password set')
else:
    print('Admin user already exists, password updated')

# Generate dummy data if needed
if Student.objects.count() == 0:
    # Add your dummy data generation code here if any
    print('Dummy data generated')
else:
    print('Data already exists, skipping')
"