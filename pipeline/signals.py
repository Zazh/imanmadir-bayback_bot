import requests
from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Buyback, BuybackResponse
from .services import format_step_message, send_telegram_message


@receiver(post_save, sender=BuybackResponse)
def on_response_approved(sender, instance, **kwargs):
    """При одобрении ответа модератором"""

    if instance.status != BuybackResponse.Status.APPROVED:
        return

    buyback = instance.buyback

    if buyback.status != Buyback.Status.ON_MODERATION:
        return

    if instance.step.order != buyback.current_step:
        return

    next_step = buyback.task.steps.filter(order__gt=buyback.current_step).order_by('order').first()

    if next_step:
        buyback.current_step = next_step.order
        buyback.status = Buyback.Status.IN_PROGRESS
        buyback.save(update_fields=['current_step', 'status'])

        total_steps = buyback.task.steps.count()
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
        return  # Новый объект

    try:
        old_instance = Buyback.objects.get(pk=instance.pk)
    except Buyback.DoesNotExist:
        return

    # Если статус изменился на APPROVED
    if old_instance.status != Buyback.Status.APPROVED and instance.status == Buyback.Status.APPROVED:
        # Создаём выплату
        from payouts.models import Payout

        # Проверяем что выплата ещё не создана
        if not Payout.objects.filter(buyback=instance).exists():
            Payout.create_from_buyback(instance)

            # Обновляем счётчики
            instance.task.product.quantity_completed += 1
            instance.task.product.save(update_fields=['quantity_completed'])

            instance.user.total_completed += 1
            instance.user.save(update_fields=['total_completed'])

            # Уведомляем пользователя
            text = (
                '🎉 <b>Выкуп одобрен!</b>\n\n'
                f'Задание: {instance.task.title}\n'
                f'Сумма к выплате: <b>{instance.task.payout}₸</b>\n\n'
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