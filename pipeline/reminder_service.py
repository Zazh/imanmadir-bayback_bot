from datetime import datetime, timedelta, time
from django.utils import timezone
from django.conf import settings
import pytz

from .models import Buyback, ReviewReminder
from steps.models import StepType


MSK = pytz.timezone('Europe/Moscow')


def get_publish_datetime(publish_time: time) -> datetime:
    """Получить datetime публикации на сегодня или завтра по МСК"""
    now_msk = timezone.now().astimezone(MSK)
    publish_dt = MSK.localize(datetime.combine(now_msk.date(), publish_time))

    # Если время уже прошло — берём завтра
    if publish_dt <= now_msk:
        publish_dt += timedelta(days=1)

    return publish_dt


def create_reminders_for_step(buyback: Buyback, step) -> list[ReviewReminder]:
    """Создать напоминания для шага публикации отзыва"""
    if step.step_type != StepType.PUBLISH_REVIEW:
        return []

    if not step.publish_time:
        return []

    publish_dt = get_publish_datetime(step.publish_time)
    reminders = []

    # За 3 часа
    scheduled = publish_dt - timedelta(hours=3)
    if scheduled > timezone.now():
        reminders.append(ReviewReminder(
            buyback=buyback,
            step=step,
            reminder_type=ReviewReminder.ReminderType.BEFORE_3H,
            scheduled_at=scheduled,
        ))

    # За 2 часа
    scheduled = publish_dt - timedelta(hours=2)
    if scheduled > timezone.now():
        reminders.append(ReviewReminder(
            buyback=buyback,
            step=step,
            reminder_type=ReviewReminder.ReminderType.BEFORE_2H,
            scheduled_at=scheduled,
        ))

    # За 1 час
    scheduled = publish_dt - timedelta(hours=1)
    if scheduled > timezone.now():
        reminders.append(ReviewReminder(
            buyback=buyback,
            step=step,
            reminder_type=ReviewReminder.ReminderType.BEFORE_1H,
            scheduled_at=scheduled,
        ))

    # За 5 минут
    scheduled = publish_dt - timedelta(minutes=5)
    if scheduled > timezone.now():
        reminders.append(ReviewReminder(
            buyback=buyback,
            step=step,
            reminder_type=ReviewReminder.ReminderType.BEFORE_5M,
            scheduled_at=scheduled,
        ))

    # Первое напоминание о просрочке (сразу после времени публикации)
    reminders.append(ReviewReminder(
        buyback=buyback,
        step=step,
        reminder_type=ReviewReminder.ReminderType.OVERDUE,
        scheduled_at=publish_dt + timedelta(minutes=5),
    ))

    ReviewReminder.objects.bulk_create(reminders)
    return reminders


def cancel_reminders_for_buyback(buyback: Buyback):
    """Отменить все напоминания для выкупа"""
    ReviewReminder.objects.filter(
        buyback=buyback,
        sent_at__isnull=True,
        is_cancelled=False,
    ).update(is_cancelled=True)


def get_reminder_text(reminder: ReviewReminder, step) -> str:
    """Получить текст напоминания"""
    publish_time = step.publish_time.strftime('%H:%M')

    texts = {
        ReviewReminder.ReminderType.BEFORE_3H: (
            f'⏰ <b>Напоминание</b>\n\n'
            f'Не забудьте опубликовать отзыв через 3 часа (в {publish_time} МСК).'
        ),
        ReviewReminder.ReminderType.BEFORE_2H: (
            f'⏰ <b>Напоминание</b>\n\n'
            f'Не забудьте опубликовать отзыв через 2 часа (в {publish_time} МСК).'
        ),
        ReviewReminder.ReminderType.BEFORE_1H: (
            f'⏰ <b>Напоминание</b>\n\n'
            f'Скоро надо будет опубликовать отзыв (в {publish_time} МСК).'
        ),
        ReviewReminder.ReminderType.BEFORE_5M: (
            f'⏰ <b>Напоминание</b>\n\n'
            f'Через 5 минут можете публиковать отзыв!'
        ),
        ReviewReminder.ReminderType.OVERDUE: (
            f'❗ <b>Напоминание</b>\n\n'
            f'Вы забыли опубликовать отзыв. Сделайте это сейчас!\n\n'
            f'📸 Отправьте скриншот опубликованного отзыва.'
        ),
    }

    return texts.get(reminder.reminder_type, '')