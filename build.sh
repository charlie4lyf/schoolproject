#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
import os
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@sms.com', os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123'))
    print('Superuser created')
else:
    print('Superuser already exists')
"