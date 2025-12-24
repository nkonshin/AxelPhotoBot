"""Handler for image generation flow."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, TaskRepository
from bot.services.balance import BalanceService, InsufficientBalanceError
from bot.keyboards.inline import (
    CallbackData,
    confirm_keyboard,
    back_keyboard,
    main_menu_keyboard,
)
from bot.states.generation import GenerationStates

logger = logging.getLogger(__name__)

router = Router(name="generate")

# Cost per generation in tokens
GENERATION_COST = 1


@router.message(GenerationStates.waiting_prompt, F.text)
async def process_prompt(message: Message, state: FSMContext) -> None:
    """
    Process the user's prompt for image generation.
    
    Shows cost and asks for confirmation.
    """
    prompt = message.text.strip()
    
    if not prompt:
        await message.answer(
            "❌ Пожалуйста, введите описание изображения.",
            reply_markup=back_keyboard(),
        )
        return
    
    if len(prompt) > 2000:
        await message.answer(
            "❌ Описание слишком длинное. Максимум 2000 символов.",
            reply_markup=back_keyboard(),
        )
        return
    
    # Get user balance
    user_tg = message.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        
        if user is None:
            await message.answer(
                "❌ Пользователь не найден. Используйте /start",
                reply_markup=back_keyboard(),
            )
            await state.clear()
            return
        
        balance = user.tokens
    
    # Save prompt to state
    await state.update_data(prompt=prompt, user_id=user.id)
    await state.set_state(GenerationStates.confirm_generation)
    
    # Show confirmation
    await message.answer(
        text=(
            f"🎨 <b>Подтверждение генерации</b>\n\n"
            f"<b>Ваш промпт:</b>\n<i>{prompt[:500]}{'...' if len(prompt) > 500 else ''}</i>\n\n"
            f"<b>Стоимость:</b> {GENERATION_COST} 🪙\n"
            f"<b>Ваш баланс:</b> {balance} 🪙\n"
            f"<b>После генерации:</b> {balance - GENERATION_COST} 🪙\n\n"
            "Подтвердить генерацию?"
        ),
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(GenerationStates.confirm_generation, F.data == CallbackData.CONFIRM)
async def confirm_generation(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Confirm and start the generation task.
    
    - Deducts tokens
    - Creates GenerationTask with status 'pending'
    - Enqueues task to RQ
    """
    data = await state.get_data()
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    
    if not prompt or not user_id:
        await callback.message.edit_text(
            "❌ Ошибка: данные сессии потеряны. Попробуйте снова.",
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
            await balance_service.deduct_tokens(user_id, GENERATION_COST)
            
            # Create task
            task = await task_repo.create(
                user_id=user_id,
                task_type="generate",
                prompt=prompt,
                tokens_spent=GENERATION_COST,
            )
            
            logger.info(f"Created generation task {task.id} for user {user_id}")
            
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
    
    # Enqueue task to RQ (import here to avoid circular imports)
    try:
        from bot.tasks.generation import enqueue_generation_task
        enqueue_generation_task(task.id)
    except Exception as e:
        logger.error(f"Failed to enqueue task {task.id}: {e}")
        # Task is created, worker will pick it up eventually
    
    await callback.message.edit_text(
        text=(
            "✅ <b>Задача создана!</b>\n\n"
            f"🆔 ID задачи: <code>{task.id}</code>\n\n"
            "⏳ Ваше изображение генерируется...\n"
            "Я отправлю результат, когда будет готово.\n\n"
            "Это может занять 10-30 секунд."
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Генерация запущена! ⏳")


@router.callback_query(GenerationStates.confirm_generation, F.data == CallbackData.CANCEL)
async def cancel_generation(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the generation and return to menu."""
    await state.clear()
    
    await callback.message.edit_text(
        text="❌ Генерация отменена.\n\nВыберите действие:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Отменено")


@router.message(GenerationStates.waiting_prompt)
async def invalid_prompt_input(message: Message) -> None:
    """Handle non-text input when waiting for prompt."""
    await message.answer(
        "❌ Пожалуйста, отправьте текстовое описание изображения.",
        reply_markup=back_keyboard(),
    )
