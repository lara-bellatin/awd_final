from __future__ import absolute_import

import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "elearning_project.settings")
app = Celery("elearning_app", broker="redis://localhost", backend="redis://localhost")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'notify-upcoming-assignment-deadlines-daily': {
        'task': 'yourapp.tasks.notify_upcoming_assignment_deadlines',
        'schedule': crontab(hour=0, minute=0),  # every day at midnight
    },
}