from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from telegram.ext import ContextTypes

from pipeline.models import Buyback, ReviewReminder
from pipeline.reminder_service import (
    create_reminders_for_step,
    cancel_reminders_for_buyback,
    get_reminder_text,
)
from steps.models import StepType


async def check_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка и отправка напоминаний"""
    now = timezone.now()

    # Получаем напоминания которые пора отправить
    reminders = ReviewReminder.objects.filter(
        sent_at__isnull=True,
        is_cancelled=False,
        scheduled_at__lte=now,
    ).select_related(
        'buyback__user',
        'buyback__task',
        'step',
    )

    async for reminder in reminders:
        buyback = reminder.buyback

        # Проверяем статус выкупа
        if buyback.status != Buyback.Status.IN_PROGRESS:
            reminder.is_cancelled = True
            await reminder.asave(update_fields=['is_cancelled'])
            continue

        # Проверяем что на нужном шаге
        if buyback.current_step != reminder.step.order:
            reminder.is_cancelled = True
            await reminder.asave(update_fields=['is_cancelled'])
            continue

        # Для OVERDUE — проверяем лимит
        if reminder.reminder_type == ReviewReminder.ReminderType.OVERDUE:
            if reminder.overdue_count >= 5:
                reminder.is_cancelled = True
                await reminder.asave(update_fields=['is_cancelled'])
                continue

        # Отправляем
        chat_id = buyback.user.telegram_id
        text = get_reminder_text(reminder, reminder.step)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML',
            )
            print(f'[REMINDER] Sent {reminder.reminder_type} to {chat_id}')

            reminder.sent_at = now

            # Для OVERDUE — создаём следующее
            if reminder.reminder_type == ReviewReminder.ReminderType.OVERDUE:
                reminder.overdue_count += 1
                await reminder.asave(update_fields=['sent_at', 'overdue_count'])

                if reminder.overdue_count < 5:
                    await ReviewReminder.objects.acreate(
                        buyback=buyback,
                        step=reminder.step,
                        reminder_type=ReviewReminder.ReminderType.OVERDUE,
                        scheduled_at=now + timedelta(hours=2),
                        overdue_count=reminder.overdue_count,
                    )
            else:
                await reminder.asave(update_fields=['sent_at'])

        except Exception as e:
            print(f'[REMINDER] Error sending to {chat_id}: {e}')


async def schedule_publish_review_reminders(application, buyback: Buyback, step):
    """Создать и запланировать напоминания для шага публикации отзыва"""
    if step.step_type != StepType.PUBLISH_REVIEW:
        return

    if not step.publish_time:
        return

    # Создаём напоминания в БД
    from asgiref.sync import sync_to_async
    await sync_to_async(create_reminders_for_step)(buyback, step)

    # Отправляем первое сообщение
    chat_id = buyback.user.telegram_id
    publish_time_str = step.publish_time.strftime('%H:%M')

    text = (
        f'📝 <b>Публикация отзыва</b>\n\n'
        f'{step.instruction}\n\n'
        f'⏰ <b>Время публикации: {publish_time_str} МСК</b>\n\n'
        f'Я напомню тебе когда придёт время.\n\n'
        f'📸 После публикации отправь скриншот отзыва.'
    )

    try:
        await application.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
        )
    except Exception as e:
        print(f'[REMINDER] Error sending initial message: {e}')


async def cancel_buyback_reminders(application, buyback: Buyback):
    """Отменить все напоминания при завершении шага"""
    from asgiref.sync import sync_to_async
    await sync_to_async(cancel_reminders_for_buyback)(buyback)