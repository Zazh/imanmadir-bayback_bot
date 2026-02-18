from pipeline.models import BuybackResponse


def moderation_count(request):
    if request.user.is_authenticated and request.user.is_staff:
        count = BuybackResponse.objects.filter(
            status=BuybackResponse.Status.PENDING,
        ).count()
        return {'moderation_count': count}
    return {}
