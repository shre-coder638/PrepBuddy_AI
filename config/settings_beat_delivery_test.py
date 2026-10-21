from .settings import *
from celery.schedules import crontab

# Explicitly enable sending only for this isolated test configuration.
WHATSAPP_SEND_ENABLED = True

# Run only the dedicated test task, targeting Reminder #37.
# Do not include the normal production reminder tasks here.
CELERY_BEAT_SCHEDULE = {
    "isolated-reminder-37-test": {
        "task": "notifications.tasks.process_single_test_reminder",
        "schedule": crontab(minute="*"),
        "args": (37,),
    },
}
