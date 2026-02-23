from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import requests

from .models import Buyback, BuybackResponse
from .services import format_step_message
from .reminder_service import create_reminders_for_step, get_publish_time_display
from steps.models import StepType


@receiver(post_save, sender=BuybackResponse)
def on_response_moderated(sender, instance, **kwargs):
    """При модерации ответа (одобрение или отклонение)"""

    buyback = instance.buyback

    if buyback.status != Buyback.Status.ON_MODERATION:
        return

    if instance.step.order != buyback.current_step:
        return

    # Отклонение — возвращаем на текущий шаг
    if instance.status == BuybackResponse.Status.REJECTED:
        buyback.status = Buyback.Status.IN_PROGRESS
        buyback.step_started_at = timezone.now()
        buyback.reminder_sent = False
        buyback.save(update_fields=['status', 'step_started_at', 'reminder_sent'])

        text = (
            '❌ <b>Ответ отклонён</b>\n\n'
            f'📦 <b>{buyback.task.title}</b>\n'
            f'Шаг {instance.step.order}: {instance.step.title or instance.step.get_step_type_display()}\n\n'
        )
        if instance.moderator_comment:
            text += f'💬 <b>Причина:</b> {instance.moderator_comment}\n\n'
        text += 'Пожалуйста, отправь ответ заново.'

        send_telegram_message(buyback.user.telegram_id, text)
        return

    if instance.status != BuybackResponse.Status.APPROVED:
        return

    next_step = buyback.task.steps.filter(order__gt=buyback.current_step).order_by('order').first()

    if next_step:
        buyback.current_step = next_step.order
        buyback.status = Buyback.Status.IN_PROGRESS
        buyback.step_started_at = timezone.now()
        buyback.reminder_sent = False
        buyback.save(update_fields=['current_step', 'status', 'step_started_at', 'reminder_sent'])

        total_steps = buyback.task.steps.count()

        # Для шага публикации отзыва — особая обработка
        if next_step.step_type == StepType.PUBLISH_REVIEW and (buyback.custom_publish_at or next_step.publish_time):
            # Создаём напоминания
            create_reminders_for_step(buyback, next_step)

            time_display = get_publish_time_display(buyback, next_step)
            text = (
                '✅ <b>Модератор одобрил!</b>\n\n'
                f'📦 <b>{buyback.task.title}</b>\n'
                f'Шаг {next_step.order} из {total_steps}\n\n'
            )
            if next_step.title:
                text += f'<b>{next_step.title}</b>\n\n'
            text += next_step.instruction
            text += f'\n\n⏰ <b>Время публикации: {time_display}</b>'
            text += '\n\nЯ напомню тебе когда придёт время.'
            text += '\n\n📸 После публикации отправь скриншот отзыва.'
        else:
            text = format_step_message(
                buyback.task,
                next_step,
                total_steps,
                prefix='✅ <b>Модератор одобрил!</b>\n\n'
            )
    else:
        buyback.status = Buyback.Status.PENDING_REVIEW
        buyback.save(update_fields=['status'])

        text = (
            '🎉 <b>Все шаги выполнены!</b>\n\n'
            'Твой выкуп отправлен на финальную проверку.'
        )

    send_telegram_message(buyback.user.telegram_id, text)


@receiver(pre_save, sender=Buyback)
def on_buyback_status_change(sender, instance, **kwargs):
    """При изменении статуса выкупа"""

    if not instance.pk:
        return

    try:
        old_instance = Buyback.objects.get(pk=instance.pk)
    except Buyback.DoesNotExist:
        return

    if old_instance.status != Buyback.Status.APPROVED and instance.status == Buyback.Status.APPROVED:
        from payouts.models import Payout

        if not Payout.objects.filter(buyback=instance).exists():
            Payout.create_from_buyback(instance)

            instance.task.product.quantity_completed += 1
            instance.task.product.save(update_fields=['quantity_completed'])

            instance.user.total_completed += 1
            instance.user.save(update_fields=['total_completed'])

            text = (
                '🎉 <b>Выкуп одобрен!</b>\n\n'
                f'Задание: {instance.task.title}\n'
                f'Сумма к выплате: <b>{instance.task.payout}₽</b>\n\n'
                'Выплата поступит в ближайшее время.'
            )
            send_telegram_message(instance.user.telegram_id, text)


def send_telegram_message(chat_id: int, text: str):
    """Отправка сообщения в Telegram"""
    url = f'https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage'

    try:
        requests.post(url, data={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
        }, timeout=10)
    except Exception as e:
        print(f'Telegram send error: {e}')