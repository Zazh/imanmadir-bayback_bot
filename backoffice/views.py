from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from account.models import TelegramUser
from catalog.models import Product, Task
from payouts.models import Payout
from pipeline.models import Buyback, BuybackResponse
from steps.models import TaskStep, StepType

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
    def get(self, request):
        form = TaskForm()
        formset = TaskStepFormSet()
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset,
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
        })


class TaskEditView(StaffRequiredMixin, View):
    def get(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        form = TaskForm(instance=task)
        formset = TaskStepFormSet(instance=task)
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset, 'task': task,
        })

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        form = TaskForm(request.POST, instance=task)
        formset = TaskStepFormSet(request.POST, request.FILES, instance=task)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('backoffice:task_detail', pk=task.pk)
        return render(request, 'backoffice/tasks/form.html', {
            'form': form, 'formset': formset, 'task': task,
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
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(task__title__icontains=q) |
                Q(user__username__icontains=q) |
                Q(user__first_name__icontains=q)
            )
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/buybacks/list.html', {
            'page': page,
            'current_status': status,
            'q': q,
            'statuses': Buyback.Status.choices,
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
        is_publish_review = response.step.step_type == StepType.PUBLISH_REVIEW
        return render(request, 'backoffice/moderation/detail.html', {
            'response': response,
            'form': ModerationForm(),
            'is_publish_review': is_publish_review,
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
        qs = TelegramUser.objects.all()
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone__icontains=q) |
                Q(telegram_id__icontains=q)
            )
        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))
        return render(request, 'backoffice/users/list.html', {'page': page, 'q': q})


class UserDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(TelegramUser, pk=pk)
        buybacks = user.buybacks.select_related('task', 'task__product').order_by('-started_at')[:20]
        return render(request, 'backoffice/users/detail.html', {
            'tg_user': user, 'buybacks': buybacks,
        })
