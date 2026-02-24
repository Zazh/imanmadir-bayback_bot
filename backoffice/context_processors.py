from bonus.models import BonusMessage
from pipeline.models import Buyback, BuybackResponse



def moderation_count(request):
    if request.user.is_authenticated and request.user.is_staff:
        responses_count = BuybackResponse.objects.filter(
            status=BuybackResponse.Status.PENDING,
        ).count()
        buybacks_count = Buyback.objects.filter(
            status=Buyback.Status.PENDING_REVIEW,
        ).count()
        unread_bonus = BonusMessage.objects.filter(
            sender_type=BonusMessage.SenderType.USER,
            is_read=False,
        ).count()
        return {
            'moderation_count': responses_count + buybacks_count,
            'unread_bonus_count': unread_bonus,
        }
    return {}
