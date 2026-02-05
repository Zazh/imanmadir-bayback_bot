from telegram import Update
from telegram.ext import ContextTypes
from django.utils import timezone
from datetime import timedelta

from tasks.models import Task, Buyback
from bot.keyboards.inline import tasks_list_keyboard, task_detail_keyboard


async def check_user_limit(user, product) -> tuple[bool, str]:
    """Проверка лимита пользователя на товар"""
    if product.limit_per_user == 0:
        return True, ''

    queryset = Buyback.objects.filter(
        user=user,
        task__product=product,
        status__in=[
            Buyback.Status.IN_PROGRESS,
            Buyback.Status.ON_REVIEW,
            Buyback.Status.COMPLETED,
            Buyback.Status.PAID,
        ]
    )

    if product.limit_per_user_days > 0:
        since = timezone.now() - timedelta(days=product.limit_per_user_days)
        queryset = queryset.filter(started_at__gte=since)

    count = await queryset.acount()

    if count >= product.limit_per_user:
        return False, product.get_limit_display()

    return True, ''


async def tasks_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список доступных заданий"""
    from account.models import TelegramUser

    user_id = update.effective_user.id

    try:
        user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text('⚠️ Профиль не найден. Нажми /start')
        return

    tasks = []
    async for task in Task.objects.filter(
            is_active=True,
            product__is_active=True
    ).select_related('product'):
        # Проверяем доступность товара
        available = await task.product.aget_quantity_available()
        if available <= 0:
            continue

        # Проверяем лимит пользователя
        can_take, _ = await check_user_limit(user, task.product)
        if not can_take:
            continue

        # Проверяем нет ли активного выкупа
        has_active = await Buyback.objects.filter(
            task=task,
            user=user,
            status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
        ).aexists()

        if not has_active:
            tasks.append(task)

    if not tasks:
        await update.message.reply_text(
            '📋 <b>Доступные задания</b>\n\n'
            'Сейчас нет доступных заданий. Загляни позже!',
            parse_mode='HTML'
        )
        return

    await update.message.reply_text(
        '📋 <b>Доступные задания</b>\n\n'
        'Выбери задание для просмотра:',
        parse_mode='HTML',
        reply_markup=tasks_list_keyboard(tasks)
    )


async def task_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали задания (callback)"""
    from account.models import TelegramUser

    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(':')[1])
    user_id = update.effective_user.id

    try:
        user = await TelegramUser.objects.aget(telegram_id=user_id)
        task = await Task.objects.select_related('product').aget(id=task_id)
    except (TelegramUser.DoesNotExist, Task.DoesNotExist):
        await query.edit_message_text('⚠️ Задание не найдено')
        return

    # Проверки
    available_flag = True
    warning = ''

    # Проверяем количество товара
    available = await task.product.aget_quantity_available()
    if available <= 0:
        available_flag = False
        warning = '⚠️ Товар закончился'

    # Проверяем лимит пользователя
    if available_flag:
        can_take, limit_msg = await check_user_limit(user, task.product)
        if not can_take:
            available_flag = False
            warning = f'⚠️ Лимит исчерпан: {limit_msg}'

    # Проверяем активный выкуп
    if available_flag:
        has_active = await Buyback.objects.filter(
            task=task,
            user=user,
            status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
        ).aexists()
        if has_active:
            available_flag = False
            warning = '⚠️ У тебя уже есть активный выкуп этого задания'

    # Собираем шаги
    steps = []
    async for step in task.steps.all().order_by('order'):
        steps.append(step)

    text = f'📦 <b>{task.title}</b>\n\n'

    text += (
        f'🏷 Товар: {task.product.name}\n'
        f'💰 Цена товара: {task.product.price}₸\n\n'
        f'💵 <b>Выплата:</b> {task.payout}₸\n\n'
    )

    # Выводим список шагов с временем
    text += f'📝 <b>Шаги ({len(steps)}):</b>\n'
    for step in steps:
        step_title = step.title if step.title else step.get_step_type_display()
        time_info = f' ({step.timeout_minutes} мин.)' if step.timeout_minutes else ''
        text += f'  {step.order}. {step_title}{time_info}\n'

    text += (
        f'\n📊 Осталось: {available} шт.\n'
        f'👤 Лимит: {task.product.get_limit_display()}\n\n'
        f'⏱ <i>Нажав «Взять задание», мы забронируем товар. '
        f'На каждый шаг отводится своё время — если не успеешь, бронь отменится.</i>'
    )

    if warning:
        text += f'\n\n{warning}'

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=task_detail_keyboard(task_id, available_flag)
    )


async def tasks_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к списку заданий (callback)"""
    from account.models import TelegramUser

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    try:
        user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await query.edit_message_text('⚠️ Профиль не найден')
        return

    tasks = []
    async for task in Task.objects.filter(
            is_active=True,
            product__is_active=True
    ).select_related('product'):
        available = await task.product.aget_quantity_available()
        if available <= 0:
            continue

        can_take, _ = await check_user_limit(user, task.product)
        if not can_take:
            continue

        has_active = await Buyback.objects.filter(
            task=task,
            user=user,
            status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
        ).aexists()

        if not has_active:
            tasks.append(task)

    if not tasks:
        await query.edit_message_text(
            '📋 <b>Доступные задания</b>\n\n'
            'Сейчас нет доступных заданий. Загляни позже!',
            parse_mode='HTML'
        )
        return

    await query.edit_message_text(
        '📋 <b>Доступные задания</b>\n\n'
        'Выбери задание для просмотра:',
        parse_mode='HTML',
        reply_markup=tasks_list_keyboard(tasks)
    )