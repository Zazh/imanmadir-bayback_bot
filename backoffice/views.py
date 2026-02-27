import requests as http_requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from account.models import TelegramUser
from bonus.models import BonusMessage
from catalog.models import Product, Task
from payouts.models import Payout
from pipeline.models import Buyback, BuybackResponse
from steps.models import TaskStep, StepType, StepTemplate, StepTemplateItem

from .forms import (
    ProductForm, TaskForm, TaskStepFormSet,
    BuybackActionForm, ModerationForm, PayoutActionForm,
)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = '/backoffice/login/'

    def test_func(self):
        return self.request.user.is_staff


# ─── Auth ────────────────────────────────────────────────────────────────────

class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('backoffice:dashboard')
        return render(request, 'backoffice/login.html')

    def post(self, request):
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            login(request, user)
            next_url = request.GET.get('next', '/backoffice/')
            return redirect(next_url)
        return render(request, 'backoffice/login.html', {'error': 'Неверные данные или нет доступа'})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('backoffice:login')


# ─── Dashboard ───────────────────────────────────────────────────────────────

class DashboardView(StaffRequiredMixin, View):
    def get(self, request):
        context = {
            'active_buybacks': Buyback.objects.filter(status=Buyback.Status.IN_PROGRESS).count(),
            'on_moderation': BuybackResponse.objects.filter(status=BuybackResponse.Status.PENDING).count(),
            'pending_review': Buyback.objects.filter(status=Buyback.Status.PENDING_REVIEW).count(),
            'pending_payouts': Payout.objects.filter(status=Payout.Status.PENDING).count(),
            'total_products': Product.objects.filter(is_active=True).count(),
            'total_users': TelegramUser.objects.count(),
            'recent_buybacks': Buyback.objects.select_related('task', 'user', 'task__product')[:10],
        }
        return render(request, 'backoffice/dashboard.html', context)


# ─── Products ────────────────────────────────────────────────────────────────

class ProductListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = Product.objects.all()
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(wb_article__icontains=q))
        is_active = request.GET.get('is_active')
        if is_active in ('1', '0'):
            qs = qs.filter(is_active=is_active == '1')
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/products/list.html', {
            'page': page, 'q': q, 'is_active': is_active,
        })


class ProductCreateView(StaffRequiredMixin, View):
    def get(self, request):
        return render(request, 'backoffice/products/form.html', {'form': ProductForm()})

    def post(self, request):
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('backoffice:product_list')
        return render(request, 'backoffice/products/form.html', {'form': form})


class ProductEditView(StaffRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        return render(request, 'backoffice/products/form.html', {
            'form': ProductForm(instance=product), 'product': product,
        })

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('backoffice:product_list')
        return render(request, 'backoffice/products/form.html', {
            'form': form, 'product': product,
        })


# ─── Tasks ───────────────────────────────────────────────────────────────────

class TaskListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = Task.objects.select_related('product').all()
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(product__name__icontains=q))
        is_active = request.GET.get('is_active')
        if is_active in ('1', '0'):
            qs = qs.filter(is_active=is_active == '1')
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/tasks/list.html', {
            'page': page, 'q': q, 'is_active': is_active,
        })


class TaskCreateView(StaffRequiredMixin, View):
    def _get_step_templates(self):
        return StepTemplate.objects.annotate(steps_count=Count('items')).all()

    def get(self, request):
        form = TaskForm()
        formset = TaskStepFormSet()
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset,
            'step_templates': self._get_step_templates(),
        })

    def post(self, request):
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            formset = TaskStepFormSet(request.POST, request.FILES, instance=task)
            if formset.is_valid():
                formset.save()
                return redirect('backoffice:task_detail', pk=task.pk)
            task.delete()
        else:
            formset = TaskStepFormSet(request.POST, request.FILES)
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset,
            'step_templates': self._get_step_templates(),
        })


class TaskEditView(StaffRequiredMixin, View):
    def _get_step_templates(self):
        return StepTemplate.objects.annotate(steps_count=Count('items')).all()

    def get(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        form = TaskForm(instance=task)
        formset = TaskStepFormSet(instance=task)
        formset.extra = 0
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset, 'task': task,
            'step_templates': self._get_step_templates(),
        })

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        form = TaskForm(request.POST, instance=task)
        formset = TaskStepFormSet(request.POST, request.FILES, instance=task)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('backoffice:task_detail', pk=task.pk)
        formset.extra = 0
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset, 'task': task,
            'step_templates': self._get_step_templates(),
        })


class TaskDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        task = get_object_or_404(Task.objects.select_related('product'), pk=pk)
        steps = task.steps.all().order_by('order')
        return render(request, 'backoffice/tasks/detail.html', {
            'task': task, 'steps': steps,
        })


# ─── Buybacks ────────────────────────────────────────────────────────────────

class BuybackListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = Buyback.objects.select_related('task', 'user', 'task__product').all()
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        step = request.GET.get('step', '')
        if step:
            qs = qs.filter(current_step=step)
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(task__title__icontains=q) |
                Q(user__username__icontains=q) |
                Q(user__first_name__icontains=q)
            )
        steps = Buyback.objects.values_list('current_step', flat=True).distinct().order_by('current_step')
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/buybacks/list.html', {
            'page': page,
            'current_status': status,
            'current_step': step,
            'q': q,
            'statuses': Buyback.Status.choices,
            'steps': steps,
        })


class BuybackDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        buyback = get_object_or_404(
            Buyback.objects.select_related('task', 'user', 'task__product'),
            pk=pk,
        )
        responses = buyback.responses.select_related('step').order_by('step__order')
        steps = buyback.task.steps.all().order_by('order')
        return render(request, 'backoffice/buybacks/detail.html', {
            'buyback': buyback,
            'responses': responses,
            'steps': steps,
            'action_form': BuybackActionForm(),
        })

    def post(self, request, pk):
        buyback = get_object_or_404(Buyback, pk=pk)
        form = BuybackActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            if action == 'approve' and buyback.status == Buyback.Status.PENDING_REVIEW:
                buyback.status = Buyback.Status.APPROVED
                buyback.save(update_fields=['status'])
            elif action == 'reject':
                reason = form.cleaned_data.get('rejection_reason', '')
                buyback.reject(reason)
        return redirect('backoffice:buyback_detail', pk=pk)


# ─── Moderation ──────────────────────────────────────────────────────────────

class ModerationListView(StaffRequiredMixin, View):
    def get(self, request):
        tab = request.GET.get('tab', 'responses')

        responses_count = BuybackResponse.objects.filter(
            status=BuybackResponse.Status.PENDING,
        ).count()
        buybacks_count = Buyback.objects.filter(
            status=Buyback.Status.PENDING_REVIEW,
        ).count()

        if tab == 'buybacks':
            qs = Buyback.objects.filter(
                status=Buyback.Status.PENDING_REVIEW,
            ).select_related('task', 'user', 'task__product').order_by('-completed_at')
        else:
            qs = BuybackResponse.objects.filter(
                status=BuybackResponse.Status.PENDING,
            ).select_related('buyback', 'buyback__task', 'buyback__user', 'step')

        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/moderation/list.html', {
            'page': page,
            'tab': tab,
            'responses_count': responses_count,
            'buybacks_count': buybacks_count,
        })


class ModerationDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        response = get_object_or_404(
            BuybackResponse.objects.select_related('buyback', 'buyback__task', 'buyback__user', 'step'),
            pk=pk,
        )
        # Показываем поля даты если следующий шаг — публикация отзыва
        next_step = response.buyback.task.steps.filter(
            order__gt=response.step.order,
        ).order_by('order').first()
        next_is_publish_review = next_step and next_step.step_type == StepType.PUBLISH_REVIEW
        return render(request, 'backoffice/moderation/detail.html', {
            'response': response,
            'form': ModerationForm(),
            'show_publish_date': next_is_publish_review,
        })

    def post(self, request, pk):
        response = get_object_or_404(
            BuybackResponse.objects.select_related('buyback'),
            pk=pk,
        )
        form = ModerationForm(request.POST)
        if form.is_valid() and response.status == BuybackResponse.Status.PENDING:
            action = form.cleaned_data['action']
            comment = form.cleaned_data.get('moderator_comment', '')
            response.moderator_comment = comment
            if action == 'approve':
                response.status = BuybackResponse.Status.APPROVED
                # Сохраняем кастомную дату публикации если указана
                pub_date = form.cleaned_data.get('publish_date')
                pub_time = form.cleaned_data.get('publish_time')
                if pub_date and pub_time:
                    import pytz
                    from datetime import datetime
                    msk = pytz.timezone('Europe/Moscow')
                    publish_dt = msk.localize(datetime.combine(pub_date, pub_time))
                    response.buyback.custom_publish_at = publish_dt
                    response.buyback.save(update_fields=['custom_publish_at'])
            elif action == 'reject':
                response.status = BuybackResponse.Status.REJECTED
            response.save(update_fields=['status', 'moderator_comment'])
        return redirect('backoffice:moderation_list')


class BuybackModerationDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        buyback = get_object_or_404(
            Buyback.objects.select_related('task', 'user', 'task__product'),
            pk=pk,
        )
        responses = buyback.responses.select_related('step').order_by('step__order')
        steps = buyback.task.steps.all().order_by('order')
        return render(request, 'backoffice/moderation/buyback_detail.html', {
            'buyback': buyback,
            'responses': responses,
            'steps': steps,
            'action_form': BuybackActionForm(),
        })

    def post(self, request, pk):
        buyback = get_object_or_404(Buyback, pk=pk)
        form = BuybackActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            if action == 'approve' and buyback.status == Buyback.Status.PENDING_REVIEW:
                buyback.status = Buyback.Status.APPROVED
                buyback.save(update_fields=['status'])
            elif action == 'reject':
                reason = form.cleaned_data.get('rejection_reason', '')
                buyback.reject(reason)
        return redirect(f'/backoffice/moderation/?tab=buybacks')


# ─── Payouts ─────────────────────────────────────────────────────────────────

class PayoutListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = Payout.objects.select_related('buyback', 'user', 'buyback__task').all()
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/payouts/list.html', {
            'page': page,
            'current_status': status,
            'statuses': Payout.Status.choices,
            'action_form': PayoutActionForm(),
        })

    def post(self, request):
        payout_id = request.POST.get('payout_id')
        payout = get_object_or_404(Payout, pk=payout_id)
        form = PayoutActionForm(request.POST)
        if form.is_valid() and payout.status in (Payout.Status.PENDING, Payout.Status.PROCESSING):
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('notes', '')
            if action == 'complete':
                payout.mark_completed(manager=request.user)
            elif action == 'fail':
                payout.mark_failed(manager=request.user, notes=notes)
        return redirect('backoffice:payout_list')


# ─── Users ───────────────────────────────────────────────────────────────────

class UserListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = TelegramUser.objects.annotate(
            buyback_count=Count('buybacks'),
            bonus_msg_count=Count('bonus_messages'),
            unread_bonus=Count(
                'bonus_messages',
                filter=Q(
                    bonus_messages__sender_type=BonusMessage.SenderType.USER,
                    bonus_messages__is_read=False,
                ),
            ),
        )
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone__icontains=q) |
                Q(telegram_id__icontains=q)
            )
        source = request.GET.get('source', '')
        if source == 'bayback':
            qs = qs.filter(buyback_count__gt=0)
        elif source == 'bonus':
            qs = qs.filter(bonus_msg_count__gt=0)
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/users/list.html', {
            'page': page, 'q': q, 'source': source,
        })


class UserDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(TelegramUser, pk=pk)
        buybacks = user.buybacks.select_related('task', 'task__product').order_by('-started_at')[:20]
        chat_messages = user.bonus_messages.all().order_by('created_at')

        user.bonus_messages.filter(
            sender_type=BonusMessage.SenderType.USER,
            is_read=False,
        ).update(is_read=True)

        last_msg = chat_messages.last()
        return render(request, 'backoffice/users/detail.html', {
            'tg_user': user,
            'buybacks': buybacks,
            'chat_messages': chat_messages,
            'last_message_id': last_msg.id if last_msg else 0,
        })


# ─── Step Templates ──────────────────────────────────────────────────────────

class SaveStepsAsTemplateView(StaffRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        name = request.POST.get('template_name', '').strip()
        if not name:
            messages.error(request, 'Укажите название шаблона')
            return redirect('backoffice:task_detail', pk=pk)
        if StepTemplate.objects.filter(name=name).exists():
            messages.error(request, f'Шаблон «{name}» уже существует')
            return redirect('backoffice:task_detail', pk=pk)

        template = StepTemplate.objects.create(name=name)
        steps = task.steps.all().order_by('order')
        for step in steps:
            StepTemplateItem.objects.create(
                template=template,
                order=step.order,
                title=step.title,
                step_type=step.step_type,
                instruction=step.instruction,
                image=step.image.name if step.image else '',
                settings=step.settings,
                publish_time=step.publish_time,
                timeout_minutes=step.timeout_minutes,
                reminder_minutes=step.reminder_minutes,
                reminder_text=step.reminder_text,
                requires_moderation=step.requires_moderation,
            )
        messages.success(request, f'Шаблон «{name}» сохранён ({steps.count()} шагов)')
        return redirect('backoffice:task_detail', pk=pk)


class StepTemplateListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = StepTemplate.objects.annotate(steps_count=Count('items')).all()
        return render(request, 'backoffice/step_templates/list.html', {
            'templates': qs,
        })


class StepTemplateDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        template = get_object_or_404(StepTemplate, pk=pk)
        name = template.name
        template.delete()
        messages.success(request, f'Шаблон «{name}» удалён')
        return redirect('backoffice:step_template_list')


class StepTemplateDataView(StaffRequiredMixin, View):
    def get(self, request, pk):
        template = get_object_or_404(StepTemplate, pk=pk)
        items = template.items.order_by('order')
        data = {
            'name': template.name,
            'steps': [
                {
                    'order': item.order,
                    'title': item.title,
                    'step_type': item.step_type,
                    'instruction': item.instruction,
                    'publish_time': item.publish_time.strftime('%H:%M') if item.publish_time else '',
                    'timeout_minutes': item.timeout_minutes or '',
                    'reminder_minutes': item.reminder_minutes or '',
                    'reminder_text': item.reminder_text,
                    'requires_moderation': item.requires_moderation,
                    'correct_article': item.settings.get('correct_article', ''),
                    'min_length': item.settings.get('min_length', ''),
                    'choices_text': '\n'.join(item.settings.get('choices', [])),
                }
                for item in items
            ],
        }
        return JsonResponse(data)


# ─── Bonus Bot ──────────────────────────────────────────────────────────────

class BonusUserListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = TelegramUser.objects.filter(bonus_bot_user=True).annotate(
            bonus_msg_count=Count('bonus_messages'),
            unread_bonus=Count(
                'bonus_messages',
                filter=Q(
                    bonus_messages__sender_type=BonusMessage.SenderType.USER,
                    bonus_messages__is_read=False,
                ),
            ),
        )
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(telegram_id__icontains=q)
            )
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/bonus/user_list.html', {
            'page': page, 'q': q,
        })


class BonusChatView(StaffRequiredMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(TelegramUser, pk=pk)
        chat_messages = user.bonus_messages.all().order_by('created_at')

        user.bonus_messages.filter(
            sender_type=BonusMessage.SenderType.USER,
            is_read=False,
        ).update(is_read=True)

        last_msg = chat_messages.last()
        return render(request, 'backoffice/bonus/chat.html', {
            'bonus_user': user,
            'chat_messages': chat_messages,
            'last_message_id': last_msg.id if last_msg else 0,
        })

    def post(self, request, pk):
        user = get_object_or_404(TelegramUser, pk=pk)
        text = request.POST.get('message', '').strip()
        if not text:
            messages.error(request, 'Сообщение не может быть пустым')
            return redirect('backoffice:bonus_chat', pk=pk)

        telegram_message_id = None
        try:
            resp = http_requests.post(
                f'https://api.telegram.org/bot{settings.BONUS_BOT_TOKEN}/sendMessage',
                json={
                    'chat_id': user.telegram_id,
                    'text': text,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                telegram_message_id = data['result']['message_id']
            else:
                messages.warning(
                    request,
                    f'Telegram API: {data.get("description", "Unknown error")}'
                )
        except http_requests.RequestException as e:
            messages.warning(request, f'Ошибка отправки: {e}')

        BonusMessage.objects.create(
            user=user,
            sender_type=BonusMessage.SenderType.MANAGER,
            text=text,
            is_read=True,
            telegram_message_id=telegram_message_id,
        )

        return redirect('backoffice:bonus_chat', pk=pk)


class BonusChatSendView(StaffRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(TelegramUser, pk=pk)
        text = request.POST.get('message', '').strip()
        if not text:
            messages.error(request, 'Сообщение не может быть пустым')
            return redirect('backoffice:user_detail', pk=pk)

        telegram_message_id = None
        try:
            resp = http_requests.post(
                f'https://api.telegram.org/bot{settings.BONUS_BOT_TOKEN}/sendMessage',
                json={
                    'chat_id': user.telegram_id,
                    'text': text,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                telegram_message_id = data['result']['message_id']
            else:
                messages.warning(
                    request,
                    f'Telegram API: {data.get("description", "Unknown error")}'
                )
        except http_requests.RequestException as e:
            messages.warning(request, f'Ошибка отправки: {e}')

        BonusMessage.objects.create(
            user=user,
            sender_type=BonusMessage.SenderType.MANAGER,
            text=text,
            is_read=True,
            telegram_message_id=telegram_message_id,
        )

        return redirect('backoffice:user_detail', pk=pk)


class BonusChatMessagesAPI(StaffRequiredMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(TelegramUser, pk=pk)
        try:
            after_id = int(request.GET.get('after', 0))
        except (ValueError, TypeError):
            after_id = 0

        new_messages = user.bonus_messages.filter(id__gt=after_id).order_by('created_at')

        new_messages.filter(
            sender_type=BonusMessage.SenderType.USER,
            is_read=False,
        ).update(is_read=True)

        data = [
            {
                'id': m.id,
                'sender_type': m.sender_type,
                'text': m.text,
                'created_at': m.created_at.strftime('%H:%M'),
            }
            for m in new_messages
        ]
        return JsonResponse({'messages': data})
