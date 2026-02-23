from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from telegram.ext import ContextTypes

from pipeline.models import Buyback, ReviewReminder
from pipeline.reminder_service import (
    create_reminders_for_step,
    cancel_reminders_for_buyback,
    get_reminder_text,
    get_publish_time_display,
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
        text = get_reminder_text(reminder, reminder.step, buyback)

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

    if not buyback.custom_publish_at and not step.publish_time:
        return

    # Создаём напоминания в БД
    from asgiref.sync import sync_to_async
    await sync_to_async(create_reminders_for_step)(buyback, step)

    # Отправляем первое сообщение
    chat_id = buyback.user.telegram_id
    time_display = get_publish_time_display(buyback, step)

    text = (
        f'📝 <b>Публикация отзыва</b>\n\n'
        f'{step.instruction}\n\n'
        f'⏰ <b>Время публикации: {time_display}</b>\n\n'
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


async def check_timeouts_job(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка таймаутов шагов — помечаем как EXPIRED"""
    from steps.models import TaskStep

    buybacks = Buyback.objects.filter(
        status=Buyback.Status.IN_PROGRESS,
        step_started_at__isnull=False,
    ).select_related('user', 'task')

    async for buyback in buybacks:
        step = await TaskStep.objects.filter(
            task_id=buyback.task_id,
            order=buyback.current_step,
        ).afirst()

        if not step or not step.timeout_minutes:
            continue

        deadline = buyback.step_started_at + timedelta(minutes=step.timeout_minutes)
        if timezone.now() <= deadline:
            continue

        # Таймаут истёк
        buyback.status = Buyback.Status.EXPIRED
        await buyback.asave(update_fields=['status'])

        try:
            await context.bot.send_message(
                chat_id=buyback.user.telegram_id,
                text=(
                    f'⏰ <b>Время истекло!</b>\n\n'
                    f'Задание «{buyback.task.title}» отменено — '
                    f'шаг не выполнен за {step.timeout_minutes} мин.'
                ),
                parse_mode='HTML',
            )
            print(f'[TIMEOUT] Buyback #{buyback.id} expired')
        except Exception as e:
            print(f'[TIMEOUT] Error notifying {buyback.user.telegram_id}: {e}')


async def check_step_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая отправка напоминаний по шагам (reminder_minutes)"""
    from steps.models import TaskStep

    buybacks = Buyback.objects.filter(
        status=Buyback.Status.IN_PROGRESS,
        step_started_at__isnull=False,
        reminder_sent=False,
    ).select_related('user', 'task')

    async for buyback in buybacks:
        step = await TaskStep.objects.filter(
            task_id=buyback.task_id,
            order=buyback.current_step,
        ).afirst()

        if not step or not step.reminder_minutes:
            continue

        remind_at = buyback.step_started_at + timedelta(minutes=step.reminder_minutes)
        if timezone.now() < remind_at:
            continue

        # Пора напомнить
        buyback.reminder_sent = True
        await buyback.asave(update_fields=['reminder_sent'])

        # Формируем текст
        if step.reminder_text:
            remaining = ''
            if step.timeout_minutes:
                left = step.timeout_minutes - step.reminder_minutes
                if left > 0:
                    remaining = f'{left} мин'
            text = step.reminder_text.format(
                remaining_time=remaining,
                task_title=buyback.task.title,
                step_title=step.title or f'Шаг {step.order}',
            )
        else:
            text = (
                f'⏰ <b>Напоминание</b>\n\n'
                f'Не забудь выполнить шаг в задании «{buyback.task.title}».'
            )
            if step.timeout_minutes:
                left = step.timeout_minutes - step.reminder_minutes
                if left > 0:
                    text += f'\nОсталось времени: {left} мин.'

        try:
            await context.bot.send_message(
                chat_id=buyback.user.telegram_id,
                text=text,
                parse_mode='HTML',
            )
            print(f'[STEP_REMINDER] Sent to {buyback.user.telegram_id} for buyback #{buyback.id}')
        except Exception as e:
            print(f'[STEP_REMINDER] Error: {e}')