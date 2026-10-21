from .settings import *

CELERY_BEAT_SCHEDULE = {
    "scheduler-heartbeat-every-minute": {
        "task": "notifications.tasks.scheduler_heartbeat",
        "schedule": crontab(minute="*"),
    },
}
