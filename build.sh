#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py shell -c "
from smsapp.models import Student
import os
if Student.objects.count() == 0:
    from django.core.management import call_command
    call_command('generate_dummy_data')
    # Update admin password to use the env var instead of hardcoded admin123
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admin = User.objects.get(username='admin')
    admin.set_password(os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123'))
    admin.save()
    print('Dummy data generated and admin password set')
else:
    print('Data already exists, skipping')
"