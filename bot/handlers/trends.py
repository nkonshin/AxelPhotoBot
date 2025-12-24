"""Handler for Ideas and Trends (Идеи и тренды)."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, TaskRepository
from bot.services.balance import BalanceService, InsufficientBalanceError
from bot.templates.prompts import get_template_by_id, get_all_templates
from bot.keyboards.inline import (
    CallbackData,
    templates_keyboard,
    confirm_keyboard,
    back_keyboard,
    main_menu_keyboard,
)
from bot.states.generation import TemplateStates

logger = logging.getLogger(__name__)

router = Router(name="trends")


# Note: Main trends menu is handled in menu.py
# This router handles template selection and confirmation


@router.callback_query(F.data.startswith(CallbackData.TEMPLATE_PREFIX))
async def select_template(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle template selection from trends menu."""
    # Extract template_id from callback data
    template_id = callback.data.replace(CallbackData.TEMPLATE_PREFIX, "")
    
    template = get_template_by_id(template_id)
    
    if template is None:
        await callback.answer("❌ Шаблон не найден")
        return
    
    # Get user info and balance
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await callback.message.edit_text(
                "❌ Пользователь не найден. Используйте /start",
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer()
            return
        
        balance = user.tokens
    
    # Save template to state
    await state.update_data(
        template_id=template_id,
        user_id=user.id,
    )
    await state.set_state(TemplateStates.confirm_template)
    
    # Show template details and confirmation
    await callback.message.edit_text(
        text=(
            f"💡 <b>{template.name}</b>\n\n"
            f"<b>Описание:</b>\n{template.description}\n\n"
            f"<b>Промпт:</b>\n<i>{template.prompt[:300]}{'...' if len(template.prompt) > 300 else ''}</i>\n\n"
            f"<b>Стоимость:</b> {template.tokens_cost} 🪙\n"
            f"<b>Ваш баланс:</b> {balance} 🪙\n"
            f"<b>После генерации:</b> {balance - template.tokens_cost} 🪙\n\n"
            "Создать изображение по этому шаблону?"
        ),
        reply_markup=confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(TemplateStates.confirm_template, F.data == CallbackData.CONFIRM)
async def confirm_template_generation(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Confirm and start generation from template.
    
    - Deducts tokens
    - Creates GenerationTask with template prompt
    - Enqueues task to RQ
    """
    data = await state.get_data()
    template_id = data.get("template_id")
    user_id = data.get("user_id")
    
    if not template_id or not user_id:
        await callback.message.edit_text(
            "❌ Ошибка: данные сессии потеряны. Попробуйте снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return
    
    template = get_template_by_id(template_id)
    
    if template is None:
        await callback.message.edit_text(
            "❌ Шаблон не найден.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        balance_service = BalanceService(session)
        task_repo = TaskRepository(session)
        
        try:
            # Deduct tokens
            await balance_service.deduct_tokens(user_id, template.tokens_cost)
            
            # Create task with template prompt
            task = await task_repo.create(
                user_id=user_id,
                task_type="generate",
                prompt=template.prompt,
                tokens_spent=template.tokens_cost,
            )
            
            logger.info(
                f"Created template task {task.id} for user {user_id} "
                f"(template: {template_id})"
            )
            
        except InsufficientBalanceError as e:
            await callback.message.edit_text(
                text=(
                    f"❌ <b>Недостаточно токенов</b>\n\n"
                    f"Требуется: {e.required} 🪙\n"
                    f"Ваш баланс: {e.available} 🪙\n\n"
                    "Пополните баланс в разделе «Купить токены»"
                ),
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            await callback.answer()
            return
    
    # Clear state
    await state.clear()
    
    # Enqueue task to RQ
    try:
        from bot.tasks.generation import enqueue_generation_task
        enqueue_generation_task(task.id)
    except Exception as e:
        logger.error(f"Failed to enqueue task {task.id}: {e}")
    
    await callback.message.edit_text(
        text=(
            f"✅ <b>Задача создана!</b>\n\n"
            f"🆔 ID задачи: <code>{task.id}</code>\n"
            f"📝 Шаблон: {template.name}\n\n"
            "⏳ Ваше изображение генерируется...\n"
            "Я отправлю результат, когда будет готово.\n\n"
            "Это может занять 10-30 секунд."
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Генерация запущена! ⏳")


@router.callback_query(TemplateStates.confirm_template, F.data == CallbackData.CANCEL)
async def cancel_template_generation(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel template generation and return to templates list."""
    await state.clear()
    
    await callback.message.edit_text(
        text=(
            "💡 <b>Идеи и тренды</b>\n\n"
            "Выберите готовый шаблон для быстрой генерации:"
        ),
        reply_markup=templates_keyboard(),
    )
    await callback.answer("Отменено")
