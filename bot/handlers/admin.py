"""Admin handlers for bot management and statistics.

Commands:
- /admin - Show admin menu
- /stats - Show bot statistics
- /broadcast - Send message to all users
- /addtokens <user_id> <amount> - Add tokens to user
"""

import asyncio
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from bot.config import config
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, StatsRepository
from bot.states.admin import BroadcastStates

logger = logging.getLogger(__name__)

router = Router(name="admin")


# Redis functions for subscription toggle
async def get_subscription_required() -> bool:
    """Get subscription requirement status from Redis."""
    try:
        import redis.asyncio as redis
        r = redis.from_url(config.redis_url)
        value = await r.get("subscription_required")
        await r.close()
        if value is None:
            return config.subscription_required
        return value.decode() == "true"
    except Exception as e:
        logger.error(f"Failed to get subscription_required from Redis: {e}")
        return config.subscription_required


async def set_subscription_required(value: bool) -> None:
    """Set subscription requirement status in Redis."""
    try:
        import redis.asyncio as redis
        r = redis.from_url(config.redis_url)
        await r.set("subscription_required", "true" if value else "false")
        await r.close()
    except Exception as e:
        logger.error(f"Failed to set subscription_required in Redis: {e}")


# Admin help text
ADMIN_HELP_TEXT = """
🔐 <b>Админ-команды</b>

📊 <b>Статистика:</b>
/admin — Админ-панель с кнопками
/stats — Статистика бота (пользователи, генерации)

👥 <b>Пользователи:</b>
/userinfo &lt;@username|telegram_id&gt; — Информация о пользователе
/addtokens &lt;@username|telegram_id&gt; &lt;amount&gt; — Добавить токены
/resetuser &lt;@username|telegram_id&gt; — Сбросить пользователя

📢 <b>Рассылка:</b>
/broadcast — Отправить сообщение всем пользователям

⚙️ <b>Настройки:</b>
/togglesub — Вкл/выкл проверку подписки на канал
/adminhelp — Эта справка
"""


def admin_required(func):
    """Decorator to check if user is admin."""
    async def wrapper(message: Message, *args, **kwargs):
        if not config.is_admin(message.from_user.id):
            await message.answer("❌ У вас нет доступа к этой команде.")
            return
        return await func(message, *args, **kwargs)
    return wrapper


def admin_menu_keyboard():
    """Create admin menu keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="admin:stats",
        ),
        InlineKeyboardButton(
            text="👥 Топ пользователей",
            callback_data="admin:top_users",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📈 Использование моделей",
            callback_data="admin:model_usage",
        ),
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="admin:refresh",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Справка",
            callback_data="admin:help",
        ),
        InlineKeyboardButton(
            text="🔔 Подписка",
            callback_data="admin:togglesub",
        ),
    )
    
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    """Show admin menu."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        text=(
            "🔐 <b>Админ-панель</b>\n\n"
            "Выберите действие:"
        ),
        reply_markup=admin_menu_keyboard(),
    )


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    """Show bot statistics."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await _send_stats(message)


async def _send_stats(message_or_callback) -> None:
    """Send statistics message."""
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        stats_repo = StatsRepository(session)
        stats = await stats_repo.get_full_stats()
    
    # Format status counts
    status_text = "\n".join([
        f"  • {status}: {count}"
        for status, count in stats["tasks_by_status"].items()
    ]) or "  Нет данных"
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"<b>Пользователи:</b>\n"
        f"  • Всего: {stats['total_users']}\n"
        f"  • Новых сегодня: {stats['users_today']}\n"
        f"  • Активных сегодня: {stats['active_users_today']}\n\n"
        f"<b>Задачи:</b>\n"
        f"  • Всего: {stats['total_tasks']}\n"
        f"  • Сегодня: {stats['tasks_today']}\n\n"
        f"<b>По статусам:</b>\n{status_text}\n\n"
        f"<b>Токены:</b>\n"
        f"  • Потрачено всего: {stats['total_tokens_spent']:,} 🪙\n\n"
        f"<i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"
    )
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(
            text=text,
            reply_markup=admin_menu_keyboard(),
        )
        await message_or_callback.answer("Статистика обновлена")
    else:
        await message_or_callback.answer(
            text=text,
            reply_markup=admin_menu_keyboard(),
        )


@router.callback_query(F.data == "admin:stats")
async def admin_stats_callback(callback: CallbackQuery) -> None:
    """Handle stats button click."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    await _send_stats(callback)


@router.callback_query(F.data == "admin:refresh")
async def admin_refresh_callback(callback: CallbackQuery) -> None:
    """Handle refresh button click."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    await _send_stats(callback)


@router.callback_query(F.data == "admin:top_users")
async def admin_top_users_callback(callback: CallbackQuery) -> None:
    """Show top users by task count."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        stats_repo = StatsRepository(session)
        top_users = await stats_repo.get_top_users(limit=10)
    
    if not top_users:
        text = "👥 <b>Топ пользователей</b>\n\nНет данных"
    else:
        users_text = "\n".join([
            f"{i}. @{user.username or '—'} (<code>{user.telegram_id}</code>) — {user.task_count} задач"
            for i, user in enumerate(top_users, 1)
        ])
        text = f"👥 <b>Топ 10 пользователей</b>\n\n{users_text}"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin:back",
        )
    )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:model_usage")
async def admin_model_usage_callback(callback: CallbackQuery) -> None:
    """Show model usage statistics."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        stats_repo = StatsRepository(session)
        model_usage = await stats_repo.get_model_usage()
    
    if not model_usage:
        text = "📈 <b>Использование моделей</b>\n\nНет данных"
    else:
        total = sum(model_usage.values())
        models_text = "\n".join([
            f"  • {model}: {count} ({count * 100 // total}%)"
            for model, count in sorted(model_usage.items(), key=lambda x: -x[1])
        ])
        text = f"📈 <b>Использование моделей</b>\n\n{models_text}\n\nВсего: {total}"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin:back",
        )
    )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:back")
async def admin_back_callback(callback: CallbackQuery) -> None:
    """Go back to admin menu."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    await _send_stats(callback)


@router.message(Command("addtokens"))
async def add_tokens_command(message: Message) -> None:
    """Add tokens to a user. Usage: /addtokens <@username|telegram_id> <amount>"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    # Parse arguments
    args = message.text.split()[1:]  # Remove /addtokens
    
    if len(args) != 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/addtokens @username 100</code>\n"
            "<code>/addtokens 123456789 100</code>"
        )
        return
    
    identifier = args[0]
    
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Количество токенов должно быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Количество токенов должно быть положительным")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        # Search by username or telegram_id
        if identifier.startswith("@"):
            user = await user_repo.get_by_username(identifier[1:])
        else:
            try:
                telegram_id = int(identifier)
                user = await user_repo.get_by_telegram_id(telegram_id)
            except ValueError:
                await message.answer("❌ Неверный формат ID")
                return
        
        if user is None:
            await message.answer(f"❌ Пользователь {identifier} не найден")
            return
        
        old_balance = user.tokens
        await user_repo.update_tokens(user.id, amount)
        new_balance = old_balance + amount
    
    await message.answer(
        f"✅ <b>Токены добавлены</b>\n\n"
        f"Пользователь: {user.first_name or user.username or user.telegram_id}\n"
        f"Username: @{user.username or '—'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Было: {old_balance} 🪙\n"
        f"Добавлено: +{amount} 🪙\n"
        f"Стало: {new_balance} 🪙"
    )


@router.message(Command("userinfo"))
async def user_info_command(message: Message) -> None:
    """Get user info. Usage: /userinfo <@username|telegram_id>"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/userinfo @username</code>\n"
            "<code>/userinfo 123456789</code>"
        )
        return
    
    identifier = args[0]
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        # Search by username or telegram_id
        if identifier.startswith("@"):
            user = await user_repo.get_by_username(identifier[1:])
        else:
            try:
                telegram_id = int(identifier)
                user = await user_repo.get_by_telegram_id(telegram_id)
            except ValueError:
                await message.answer("❌ Неверный формат ID")
                return
        
        if user is None:
            await message.answer(f"❌ Пользователь {identifier} не найден")
            return
        
        # Count user's tasks
        from bot.db.repositories import TaskRepository
        task_repo = TaskRepository(session)
        history = await task_repo.get_user_history(user.id, limit=100)
        
        done_count = sum(1 for t in history if t.status == "done")
        failed_count = sum(1 for t in history if t.status == "failed")
    
    await message.answer(
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"<b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Username:</b> @{user.username or '—'}\n"
        f"<b>Имя:</b> {user.first_name or '—'}\n"
        f"<b>Баланс:</b> {user.tokens} 🪙\n"
        f"<b>Модель:</b> {user.selected_model}\n"
        f"<b>Качество:</b> {user.image_quality}\n"
        f"<b>Размер:</b> {user.image_size}\n\n"
        f"<b>Задачи:</b>\n"
        f"  • Всего: {len(history)}\n"
        f"  • Успешных: {done_count}\n"
        f"  • Неудачных: {failed_count}\n\n"
        f"<b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else '—'}"
    )


@router.message(Command("adminhelp"))
async def admin_help_command(message: Message) -> None:
    """Show admin help with all available commands."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в админ-панель",
            callback_data="admin:back",
        )
    )
    
    await message.answer(
        text=ADMIN_HELP_TEXT,
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "admin:help")
async def admin_help_callback(callback: CallbackQuery) -> None:
    """Handle help button click."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в админ-панель",
            callback_data="admin:back",
        )
    )
    
    await callback.message.edit_text(
        text=ADMIN_HELP_TEXT,
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.message(Command("resetuser"))
async def reset_user_command(message: Message) -> None:
    """Reset user to default state. Usage: /resetuser <@username|telegram_id>"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/resetuser @username</code>\n"
            "<code>/resetuser 123456789</code>"
        )
        return
    
    identifier = args[0]
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        # Search by username or telegram_id
        if identifier.startswith("@"):
            user = await user_repo.get_by_username(identifier[1:])
        else:
            try:
                telegram_id = int(identifier)
                user = await user_repo.get_by_telegram_id(telegram_id)
            except ValueError:
                await message.answer("❌ Неверный формат ID")
                return
        
        if user is None:
            await message.answer(f"❌ Пользователь {identifier} не найден")
            return
        
        # Save old values for report
        old_tokens = user.tokens
        old_model = user.selected_model
        old_quality = user.image_quality
        old_size = user.image_size
        
        # Reset to defaults
        user.tokens = config.initial_tokens
        user.selected_model = "gpt-image-1.5"
        user.image_quality = "medium"
        user.image_size = "1024x1024"
        await session.commit()
    
    await message.answer(
        f"✅ <b>Пользователь сброшен</b>\n\n"
        f"<b>Пользователь:</b> {user.first_name or user.username or identifier}\n"
        f"<b>Telegram ID:</b> <code>{user.telegram_id}</code>\n\n"
        f"<b>Изменения:</b>\n"
        f"  • Токены: {old_tokens} → {config.initial_tokens}\n"
        f"  • Модель: {old_model} → gpt-image-1.5\n"
        f"  • Качество: {old_quality} → medium\n"
        f"  • Размер: {old_size} → 1024x1024"
    )


@router.message(Command("togglesub"))
async def toggle_subscription_command(message: Message) -> None:
    """Toggle subscription requirement for new users."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    current = await get_subscription_required()
    new_value = not current
    await set_subscription_required(new_value)
    
    status = "✅ включена" if new_value else "❌ выключена"
    await message.answer(
        f"🔔 <b>Проверка подписки на канал</b>\n\n"
        f"Статус: {status}\n"
        f"Канал: {config.subscription_channel or 'не задан'}\n\n"
        f"<i>Новые пользователи {'должны' if new_value else 'не должны'} подписаться на канал для получения токенов.</i>"
    )


@router.callback_query(F.data == "admin:togglesub")
async def toggle_subscription_callback(callback: CallbackQuery) -> None:
    """Handle toggle subscription button click."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    current = await get_subscription_required()
    new_value = not current
    await set_subscription_required(new_value)
    
    status = "✅ включена" if new_value else "❌ выключена"
    await callback.answer(f"Проверка подписки: {status}")
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin:back",
        )
    )
    
    await callback.message.edit_text(
        text=(
            f"🔔 <b>Проверка подписки на канал</b>\n\n"
            f"Статус: {status}\n"
            f"Канал: {config.subscription_channel or 'не задан'}\n\n"
            f"<i>Новые пользователи {'должны' if new_value else 'не должны'} подписаться на канал для получения токенов.</i>"
        ),
        reply_markup=builder.as_markup(),
    )



# ============== Broadcast handlers ==============

@router.message(Command("broadcast"))
async def broadcast_command(message: Message, state: FSMContext) -> None:
    """Start broadcast flow."""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await state.set_state(BroadcastStates.waiting_message)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="broadcast:cancel",
        )
    )
    
    await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте сообщение, которое хотите разослать всем пользователям.\n\n"
        "Поддерживается:\n"
        "• Текст с форматированием\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n\n"
        "<i>Для отмены нажмите кнопку ниже или отправьте /cancel</i>",
        reply_markup=builder.as_markup(),
    )


@router.message(Command("cancel"), BroadcastStates.waiting_message)
@router.message(Command("cancel"), BroadcastStates.confirm_broadcast)
async def broadcast_cancel_command(message: Message, state: FSMContext) -> None:
    """Cancel broadcast via command."""
    await state.clear()
    await message.answer("❌ Рассылка отменена")


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel broadcast via button."""
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer()


@router.message(BroadcastStates.waiting_message)
async def broadcast_receive_message(message: Message, state: FSMContext) -> None:
    """Receive broadcast message and ask for confirmation."""
    if not config.is_admin(message.from_user.id):
        return
    
    # Store message info for later
    await state.update_data(
        message_id=message.message_id,
        chat_id=message.chat.id,
        has_photo=message.photo is not None,
        has_video=message.video is not None,
    )
    
    await state.set_state(BroadcastStates.confirm_broadcast)
    
    # Get user count
    session_maker = get_session_maker()
    async with session_maker() as session:
        stats_repo = StatsRepository(session)
        total_users = await stats_repo.get_total_users()
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Отправить всем",
            callback_data="broadcast:confirm",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="broadcast:cancel",
        ),
    )
    
    await message.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"Сообщение будет отправлено <b>{total_users}</b> пользователям.\n\n"
        f"Подтвердить отправку?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "broadcast:confirm", BroadcastStates.confirm_broadcast)
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Confirm and execute broadcast."""
    if not config.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    data = await state.get_data()
    await state.clear()
    
    message_id = data.get("message_id")
    chat_id = data.get("chat_id")
    
    if not message_id or not chat_id:
        await callback.message.edit_text("❌ Ошибка: сообщение не найдено")
        return
    
    await callback.message.edit_text("📤 Начинаю рассылку...")
    
    # Get all users
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_all_users()
    
    total = len(users)
    success = 0
    failed = 0
    
    # Send progress updates every 50 users
    progress_message = await callback.message.answer(
        f"📤 Рассылка: 0/{total} (0%)"
    )
    
    from aiogram import Bot
    bot = Bot(token=config.bot_token)
    
    for i, user in enumerate(users):
        try:
            await bot.copy_message(
                chat_id=user.telegram_id,
                from_chat_id=chat_id,
                message_id=message_id,
            )
            success += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Failed to send broadcast to {user.telegram_id}: {e}")
        
        # Update progress every 50 users
        if (i + 1) % 50 == 0 or (i + 1) == total:
            percent = (i + 1) * 100 // total
            try:
                await progress_message.edit_text(
                    f"📤 Рассылка: {i + 1}/{total} ({percent}%)\n"
                    f"✅ Успешно: {success}\n"
                    f"❌ Ошибок: {failed}"
                )
            except Exception:
                pass
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.05)
    
    await bot.session.close()
    
    # Final report
    await progress_message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 <b>Итоги:</b>\n"
        f"  • Всего: {total}\n"
        f"  • Успешно: {success}\n"
        f"  • Ошибок: {failed}\n\n"
        f"<i>Ошибки обычно означают, что пользователь заблокировал бота.</i>"
    )


# ============== File ID helper for admins ==============

@router.message(F.video_note)
async def handle_video_note_file_id(message: Message) -> None:
    """Show file_id for video notes sent by admins."""
    if not config.is_admin(message.from_user.id):
        return
    
    file_id = message.video_note.file_id
    
    logger.info(f"Admin {message.from_user.id} sent video_note, file_id: {file_id}")
    
    await message.answer(
        f"📹 <b>Video Note File ID:</b>\n\n"
        f"<code>{file_id}</code>\n\n"
        f"Добавь в .env:\n"
        f"<code>WELCOME_VIDEO_FILE_ID={file_id}</code>",
        parse_mode="HTML"
    )


@router.message(F.photo)
async def handle_photo_file_id(message: Message) -> None:
    """Show file_id for photos sent by admins."""
    if not config.is_admin(message.from_user.id):
        return
    
    # Get the largest photo
    photo = message.photo[-1]
    file_id = photo.file_id
    
    logger.info(f"Admin {message.from_user.id} sent photo, file_id: {file_id}")
    
    await message.answer(
        f"🖼 <b>Photo File ID:</b>\n\n"
        f"<code>{file_id}</code>\n\n"
        f"Размер: {photo.width}x{photo.height}",
        parse_mode="HTML"
    )


@router.message(F.video)
async def handle_video_file_id(message: Message) -> None:
    """Show file_id for videos sent by admins."""
    if not config.is_admin(message.from_user.id):
        return
    
    file_id = message.video.file_id
    
    logger.info(f"Admin {message.from_user.id} sent video, file_id: {file_id}")
    
    await message.answer(
        f"🎥 <b>Video File ID:</b>\n\n"
        f"<code>{file_id}</code>\n\n"
        f"Размер: {message.video.width}x{message.video.height}\n"
        f"Длительность: {message.video.duration}s",
        parse_mode="HTML"
    )


@router.message(F.document)
async def handle_document_file_id(message: Message) -> None:
    """Show file_id for documents sent by admins."""
    if not config.is_admin(message.from_user.id):
        return
    
    file_id = message.document.file_id
    file_name = message.document.file_name or "unknown"
    
    logger.info(f"Admin {message.from_user.id} sent document, file_id: {file_id}")
    
    await message.answer(
        f"📄 <b>Document File ID:</b>\n\n"
        f"<code>{file_id}</code>\n\n"
        f"Имя: {file_name}",
        parse_mode="HTML"
    )
