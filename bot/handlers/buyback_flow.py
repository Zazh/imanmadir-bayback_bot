from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from account.models import TelegramUser
from tasks.models import Task, TaskStep, Buyback, BuybackResponse
from bot.states import BuybackState
from bot.keyboards.reply import main_menu_keyboard

# Состояния ConversationHandler
STEP_RESPONSE = 1


async def get_user(telegram_id: int) -> TelegramUser | None:
    try:
        return await TelegramUser.objects.aget(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


def format_remaining_time(minutes: int) -> str:
    """Форматирование оставшегося времени"""
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f'{hours} ч. {mins} мин.' if mins else f'{hours} ч.'
    return f'{minutes} мин.'


async def send_step_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминания о шаге"""
    job = context.job
    buyback_id = job.data['buyback_id']
    step_id = job.data['step_id']
    chat_id = job.data['chat_id']
    step_started_at = job.data['step_started_at']

    try:
        buyback = await Buyback.objects.select_related('task').aget(id=buyback_id)
        step = await TaskStep.objects.select_related('task').aget(id=step_id)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        return

    # Проверяем что выкуп всё ещё в процессе и на том же шаге
    if buyback.status != Buyback.Status.IN_PROGRESS:
        return
    if buyback.current_step != step.order:
        return

    # Вычисляем оставшееся время
    if step.timeout_minutes:
        deadline = step_started_at + timedelta(minutes=step.timeout_minutes)
        now = timezone.now()
        remaining = deadline - now
        remaining_minutes = max(0, int(remaining.total_seconds() // 60))
    else:
        remaining_minutes = 0

    # Формируем текст напоминания
    if step.reminder_text:
        step_title = step.title if step.title else step.get_step_type_display()
        text = step.reminder_text.format(
            remaining_time=format_remaining_time(remaining_minutes),
            task_title=buyback.task.title,
            step_title=step_title,
        )
    else:
        text = (
            f'💝 <b>Напоминание!</b>\n\n'
            f'Ты выполняешь задание «{buyback.task.title}», но пока не продолжил.\n\n'
        )
        if remaining_minutes > 0:
            text += f'⏱ Осталось времени: <b>{format_remaining_time(remaining_minutes)}</b>\n\n'
        text += 'Продолжи выполнение!'

    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')


async def check_step_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Проверка истечения времени на шаг"""
    job = context.job
    buyback_id = job.data['buyback_id']
    step_id = job.data['step_id']
    chat_id = job.data['chat_id']

    try:
        buyback = await Buyback.objects.select_related('task').aget(id=buyback_id)
        step = await TaskStep.objects.aget(id=step_id)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        return

    # Проверяем что выкуп всё ещё в процессе и на том же шаге
    if buyback.status != Buyback.Status.IN_PROGRESS:
        return
    if buyback.current_step != step.order:
        return

    # Отменяем выкуп
    buyback.status = Buyback.Status.EXPIRED
    await buyback.asave(update_fields=['status'])

    text = (
        f'⏰ <b>Время вышло!</b>\n\n'
        f'Бронь на задание «{buyback.task.title}» истекла.\n'
        f'Ты можешь взять задание заново.'
    )
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')


def schedule_step_jobs(context: ContextTypes.DEFAULT_TYPE, buyback_id: int, step: TaskStep, chat_id: int):
    """Запланировать напоминание и таймаут для шага"""
    if not context.job_queue:
        return  # JobQueue недоступен (webhook режим)

    # Если требует модерации — не ставим таймеры
    if step.requires_moderation:
        return

    step_started_at = timezone.now()

    # Отменяем старые задания
    cancel_step_jobs(context, buyback_id)

    job_data = {
        'buyback_id': buyback_id,
        'step_id': step.id,
        'chat_id': chat_id,
        'step_started_at': step_started_at,
    }

    # Напоминание
    if step.reminder_minutes:
        context.job_queue.run_once(
            send_step_reminder,
            when=step.reminder_minutes * 60,
            data=job_data,
            name=f'reminder_{buyback_id}',
        )

    # Таймаут (отмена брони)
    if step.timeout_minutes:
        context.job_queue.run_once(
            check_step_timeout,
            when=step.timeout_minutes * 60,
            data=job_data,
            name=f'timeout_{buyback_id}',
        )


def cancel_step_jobs(context: ContextTypes.DEFAULT_TYPE, buyback_id: int):
    """Отменить все задания для выкупа"""
    if not context.job_queue:
        return

    for prefix in ['reminder_', 'timeout_']:
        job_name = f'{prefix}{buyback_id}'
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()


def get_step_keyboard(step: TaskStep, buyback_id: int, user: TelegramUser = None):
    """Клавиатура для шага"""
    buttons = []

    if step.step_type == TaskStep.StepType.CONFIRM:
        buttons.append([InlineKeyboardButton('✅ Готово', callback_data=f'step_confirm:{buyback_id}')])

    elif step.step_type == TaskStep.StepType.CHOICE:
        choices = step.settings.get('choices', [])
        for choice in choices:
            buttons.append([InlineKeyboardButton(choice, callback_data=f'step_choice:{buyback_id}:{choice}')])

    elif step.step_type == TaskStep.StepType.PAYMENT_DETAILS:
        if user and user.has_payment_info:
            buttons.append([InlineKeyboardButton('✅ Оставить текущие', callback_data=f'payment_keep:{buyback_id}')])
            buttons.append([InlineKeyboardButton('✏️ Изменить реквизиты', callback_data=f'payment_change:{buyback_id}')])
        # Если реквизитов нет — просто ждём ввод текста

    buttons.append([InlineKeyboardButton('❌ Отменить выкуп', callback_data=f'cancel_buyback:{buyback_id}')])

    return InlineKeyboardMarkup(buttons)


async def show_current_step(update: Update, context: ContextTypes.DEFAULT_TYPE, buyback: Buyback):
    """Показать текущий шаг"""
    import time
    t0 = time.time()

    try:
        step = await buyback.task.steps.filter(order=buyback.current_step).afirst()
        print(f"step 1 - get step: {time.time() - t0:.3f}s")

        if not step:
            buyback.status = Buyback.Status.ON_REVIEW
            await buyback.asave(update_fields=['status'])

            cancel_step_jobs(context, buyback.id)

            text = (
                '🎉 <b>Все шаги выполнены!</b>\n\n'
                'Твой выкуп отправлен на проверку. '
                'Ожидай подтверждения и выплаты.'
            )

            if update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_menu_keyboard())

            return ConversationHandler.END

        t1 = time.time()
        task = await Task.objects.select_related('product').aget(id=buyback.task_id)
        total_steps = await task.steps.acount()
        print(f"step 2 - get task: {time.time() - t1:.3f}s")

        text = f'📦 <b>{task.title}</b>\n'
        text += f'Шаг {step.order} из {total_steps}\n\n'

        if step.title:
            text += f'<b>{step.title}</b>\n\n'

        text += f'{step.instruction}\n'

        if step.step_type == TaskStep.StepType.PHOTO:
            text += '\n📸 Отправь фото'
        elif step.step_type == TaskStep.StepType.ARTICLE_CHECK:
            text += '\n🔢 Введи артикул товара'
        elif step.step_type == TaskStep.StepType.TEXT_MODERATED:
            hint = step.settings.get('hint', '')
            if hint:
                text += f'\n💡 Подсказка: {hint}'
            text += '\n✏️ Напиши текст'
        elif step.step_type == TaskStep.StepType.ORDER_NUMBER:
            text += '\n🔢 Введи номер заказа'
        elif step.step_type == TaskStep.StepType.CHECK_LINK:
            text += '\n🔗 Отправь ссылку на чек'
        elif step.step_type == TaskStep.StepType.PAYMENT_DETAILS:
            user = await TelegramUser.objects.aget(id=buyback.user_id)
            if user.has_payment_info:
                text += f'\n\n💳 <b>Текущие реквизиты:</b>\n'
                text += f'📱 Телефон: {user.phone}\n'
                text += f'🏦 Банк: {user.bank_name}\n'
                text += f'👤 ФИО: {user.card_holder_name}\n'
                text += '\nОставить или изменить?'
            else:
                text += '\n\n📱 Введи номер телефона привязанный к банку:'
                context.user_data['payment_step'] = 'phone'

        if step.timeout_minutes and not step.requires_moderation:
            text += f'\n\n⏰ Время на выполнение: {format_remaining_time(step.timeout_minutes)}'

        context.user_data['buyback_id'] = buyback.id
        context.user_data['step_id'] = step.id
        context.user_data['step_type'] = step.step_type

        # Для реквизитов нужен user
        if step.step_type == TaskStep.StepType.PAYMENT_DETAILS:
            user = await TelegramUser.objects.aget(id=buyback.user_id)
            keyboard = get_step_keyboard(step, buyback.id, user)
        else:
            keyboard = get_step_keyboard(step, buyback.id)

        chat_id = update.effective_chat.id

        t2 = time.time()
        print(
            f"step 3 - before schedule, timeout_minutes={step.timeout_minutes}, reminder_minutes={step.reminder_minutes}")
        schedule_step_jobs(context, buyback.id, step, chat_id)
        print(f"step 4 - after schedule: {time.time() - t2:.3f}s")

        # Проверяем есть ли изображение у шага
        has_image = step.image and step.image.name
        print(f"step 5 - has_image: {has_image}")

        t3 = time.time()
        if update.callback_query:
            # Удаляем предыдущее сообщение
            try:
                await update.callback_query.delete_message()
                print(f"step 6 - deleted message: {time.time() - t3:.3f}s")
            except Exception as e:
                print(f"step 6 - delete error: {e}")

            t4 = time.time()
            if has_image:
                image_path = step.image.path
                print(f"step 7 - image path: {image_path}")
                with open(image_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=keyboard,
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode='HTML',
                    reply_markup=keyboard,
                )
            print(f"step 8 - sent message: {time.time() - t4:.3f}s")
        else:
            t4 = time.time()
            if has_image:
                image_path = step.image.path
                with open(image_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=keyboard,
                    )
            else:
                await update.message.reply_text(
                    text=text,
                    parse_mode='HTML',
                    reply_markup=keyboard,
                )
            print(f"step 8 - sent message: {time.time() - t4:.3f}s")

        print(f"TOTAL show_current_step: {time.time() - t0:.3f}s")
        print(f"DEBUG: returning STEP_RESPONSE = {STEP_RESPONSE}")
        return STEP_RESPONSE

    except Exception as e:
        import traceback
        print(f"ERROR in show_current_step: {e}")
        traceback.print_exc()
        raise


async def take_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Взять задание"""
    import time

    query = update.callback_query
    await query.answer()

    t0 = time.time()

    task_id = int(query.data.split(':')[1])
    user = await get_user(update.effective_user.id)
    print(f"1. get_user: {time.time() - t0:.3f}s")

    if not user:
        await query.edit_message_text('⚠️ Профиль не найден. Нажми /start')
        return ConversationHandler.END

    if user.is_blocked:
        await query.edit_message_text('⛔ Ваш аккаунт заблокирован.')
        return ConversationHandler.END

    t1 = time.time()
    try:
        task = await Task.objects.select_related('product').aget(id=task_id, is_active=True)
    except Task.DoesNotExist:
        await query.edit_message_text('⚠️ Задание не найдено или неактивно')
        return ConversationHandler.END
    print(f"2. get_task: {time.time() - t1:.3f}s")

    t2 = time.time()
    available = await task.product.aget_quantity_available()
    print(f"3. get_available: {time.time() - t2:.3f}s")

    if available <= 0:
        await query.edit_message_text('⚠️ Товар закончился')
        return ConversationHandler.END

    t3 = time.time()
    from bot.handlers.tasks import check_user_limit
    can_take, limit_msg = await check_user_limit(user, task.product)
    print(f"4. check_limit: {time.time() - t3:.3f}s")

    if not can_take:
        await query.edit_message_text(f'⚠️ Лимит исчерпан: {limit_msg}')
        return ConversationHandler.END

    t4 = time.time()
    has_active = await Buyback.objects.filter(
        task=task,
        user=user,
        status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
    ).aexists()
    print(f"5. check_active: {time.time() - t4:.3f}s")

    if has_active:
        await query.edit_message_text('⚠️ У тебя уже есть активный выкуп этого задания')
        return ConversationHandler.END

    t5 = time.time()

    # Получаем первый шаг задания
    first_step = await task.steps.order_by('order').afirst()
    first_step_order = first_step.order if first_step else 0

    # Создаём выкуп
    buyback = await Buyback.objects.acreate(
        task=task,
        user=user,
        current_step=first_step_order,
        status=Buyback.Status.IN_PROGRESS,
    )
    print(f"6. create_buyback: {time.time() - t5:.3f}s")

    t6 = time.time()
    new_available = await task.product.aget_quantity_available()
    total = task.product.quantity_total
    print(f"7. get_new_available: {time.time() - t6:.3f}s")

    t7 = time.time()
    await query.edit_message_text(
        f'✅ Задание взято!\n\n'
        f'💝 Товаров по акции осталось: {new_available}/{total}\n\n'
        f'Загружаю первый шаг...'
    )
    print(f"8. edit_message: {time.time() - t7:.3f}s")

    t8 = time.time()
    result = await show_current_step(update, context, buyback)
    print(f"9. show_step: {time.time() - t8:.3f}s")

    print(f"TOTAL: {time.time() - t0:.3f}s")
    return result


async def handle_step_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на шаг (фото, текст)"""
    print(f"DEBUG: handle_step_response вызван!")
    print(f"DEBUG: user_data = {context.user_data}")

    buyback_id = context.user_data.get('buyback_id')
    step_id = context.user_data.get('step_id')
    step_type = context.user_data.get('step_type')

    if not buyback_id or not step_id:
        await update.message.reply_text('⚠️ Ошибка. Начни заново через меню.')
        return ConversationHandler.END

    try:
        buyback = await Buyback.objects.select_related('task__product', 'user').aget(id=buyback_id)
        step = await TaskStep.objects.aget(id=step_id)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        await update.message.reply_text('⚠️ Ошибка. Начни заново через меню.')
        return ConversationHandler.END

    cancel_step_jobs(context, buyback_id)

    response_data = {}

    # Сравниваем со строками, т.к. step_type хранится как строка в user_data
    if step_type == 'photo':
        if not update.message.photo:
            await update.message.reply_text('📸 Отправь фото, пожалуйста')
            schedule_step_jobs(context, buyback_id, step, update.effective_chat.id)
            return STEP_RESPONSE

        photo = update.message.photo[-1]
        file = await photo.get_file()
        file_path = f'buybacks/{buyback_id}/step_{step.order}_{photo.file_id}.jpg'

        import os
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        await file.download_to_drive(full_path)

        response_data = {'photo': file_path}

    elif step_type == 'article_check':
        text = update.message.text.strip()
        correct_article = step.settings.get('correct_article') or buyback.task.product.wb_article

        if text != correct_article:
            await update.message.reply_text('❌ Артикул не совпадает. Проверь и введи ещё раз.')
            schedule_step_jobs(context, buyback_id, step, update.effective_chat.id)
            return STEP_RESPONSE

        response_data = {'value': text}

    elif step_type == 'text_moderated':
        text = update.message.text
        if len(text) < 10:
            await update.message.reply_text('✏️ Текст слишком короткий. Напиши подробнее.')
            schedule_step_jobs(context, buyback_id, step, update.effective_chat.id)
            return STEP_RESPONSE

        response_data = {'text': text}

    elif step_type == 'order_number':
        text = update.message.text.strip()
        response_data = {'value': text}

    elif step_type == 'confirm':
        # Подтверждение обрабатывается через callback кнопку
        response_data = {'confirmed': True}

    elif step_type == 'choice':
        # Выбор обрабатывается через callback кнопку
        text = update.message.text.strip()
        response_data = {'choice': text}

    elif step_type == 'check_link':
        text = update.message.text.strip()

        if not text.startswith('https://'):
            await update.message.reply_text('🔗 Отправь корректную ссылку (начинается с https://)')
            schedule_step_jobs(context, buyback_id, step, update.effective_chat.id)
            return STEP_RESPONSE

        response_data = {'link': text}

    elif step_type == 'payment_details':
        text = update.message.text.strip()
        payment_step = context.user_data.get('payment_step', 'phone')
        user = buyback.user

        if payment_step == 'phone':
            user.phone = text
            await user.asave(update_fields=['phone'])
            context.user_data['payment_step'] = 'bank'
            await update.message.reply_text('🏦 Введи название банка (например: Kaspi, Halyk, Jusan):')
            schedule_step_jobs(context, buyback_id, step, update.effective_chat.id)
            return STEP_RESPONSE

        elif payment_step == 'bank':
            user.bank_name = text
            await user.asave(update_fields=['bank_name'])
            context.user_data['payment_step'] = 'name'
            await update.message.reply_text('👤 Введи ФИО как на банковской карте:')
            schedule_step_jobs(context, buyback_id, step, update.effective_chat.id)
            return STEP_RESPONSE

        elif payment_step == 'name':
            user.card_holder_name = text
            await user.asave(update_fields=['card_holder_name'])
            context.user_data.pop('payment_step', None)

            response_data = {
                'phone': user.phone,
                'bank_name': user.bank_name,
                'card_holder_name': user.card_holder_name,
            }

    else:
        # Неизвестный тип шага
        await update.message.reply_text('⚠️ Неизвестный тип шага. Обратись к менеджеру.')
        return ConversationHandler.END

    # Определяем статус на основе настройки шага
    if step.requires_moderation:
        status = BuybackResponse.Status.PENDING
    else:
        status = BuybackResponse.Status.AUTO_APPROVED

    # Сохраняем ответ
    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data=response_data,
        status=status,
    )

    # Если требует модерации — ждём
    if status == BuybackResponse.Status.PENDING:
        await update.message.reply_text(
            '✅ Принято! Ожидай проверки модератором.',
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    # Если авто-одобрено — переходим к следующему шагу
    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def step_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки подтверждения"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])
    cancel_step_jobs(context, buyback_id)

    try:
        buyback = await Buyback.objects.select_related('task').aget(id=buyback_id)
        step = await buyback.task.steps.filter(order=buyback.current_step).afirst()
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={'confirmed': True},
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def step_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора варианта"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    buyback_id = int(parts[1])
    choice = parts[2]

    cancel_step_jobs(context, buyback_id)

    try:
        buyback = await Buyback.objects.select_related('task').aget(id=buyback_id)
        step = await buyback.task.steps.filter(order=buyback.current_step).afirst()
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={'choice': choice},
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def cancel_buyback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выкупа"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])
    cancel_step_jobs(context, buyback_id)

    try:
        buyback = await Buyback.objects.aget(id=buyback_id)
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Выкуп не найден')
        return ConversationHandler.END

    if buyback.status not in [Buyback.Status.IN_PROGRESS]:
        await query.edit_message_text('⚠️ Этот выкуп нельзя отменить')
        return ConversationHandler.END

    buyback.status = Buyback.Status.CANCELLED
    await buyback.asave(update_fields=['status'])

    await query.edit_message_text(
        '❌ Выкуп отменён.\n\n'
        'Ты можешь взять другое задание в меню.'
    )

    context.user_data.clear()
    return ConversationHandler.END

async def payment_keep_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оставить текущие реквизиты"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])
    cancel_step_jobs(context, buyback_id)

    try:
        buyback = await Buyback.objects.select_related('task', 'user').aget(id=buyback_id)
        step = await buyback.task.steps.filter(order=buyback.current_step).afirst()
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    user = buyback.user

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={
            'phone': user.phone,
            'bank_name': user.bank_name,
            'card_holder_name': user.card_holder_name,
            'kept_existing': True,
        },
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def payment_change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить реквизиты"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])

    context.user_data['buyback_id'] = buyback_id
    context.user_data['payment_step'] = 'phone'

    await query.edit_message_text(
        '📱 Введи номер телефона привязанный к банку:'
    )

    return STEP_RESPONSE

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда отмены"""
    buyback_id = context.user_data.get('buyback_id')
    if buyback_id:
        cancel_step_jobs(context, buyback_id)

    context.user_data.clear()
    await update.message.reply_text(
        'Действие отменено.',
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END