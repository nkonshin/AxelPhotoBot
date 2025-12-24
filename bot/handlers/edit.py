"""Handler for image editing flow."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
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
from bot.states.generation import EditStates

logger = logging.getLogger(__name__)

router = Router(name="edit")

# Cost per edit in tokens
EDIT_COST = 1

# Supported image formats
SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_format(file_name: str | None, mime_type: str | None) -> bool:
    """
    Validate that the image format is supported.
    
    Args:
        file_name: Original file name
        mime_type: MIME type of the file
    
    Returns:
        True if format is supported, False otherwise
    """
    # Check MIME type
    if mime_type and mime_type.lower() in SUPPORTED_FORMATS:
        return True
    
    # Check file extension
    if file_name:
        file_name_lower = file_name.lower()
        for ext in SUPPORTED_EXTENSIONS:
            if file_name_lower.endswith(ext):
                return True
    
    return False


@router.message(EditStates.waiting_image, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    """
    Process uploaded photo for editing.
    
    Saves file_id and asks for edit description.
    """
    # Get the largest photo size
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id
    
    # Get user info
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
    
    # Save photo file_id to state
    await state.update_data(
        source_file_id=file_id,
        user_id=user.id,
    )
    await state.set_state(EditStates.waiting_edit_prompt)
    
    await message.answer(
        text=(
            "✅ <b>Фото получено!</b>\n\n"
            "Теперь опишите, какие изменения вы хотите внести.\n\n"
            "💡 <i>Примеры:</i>\n"
            "• «Сделай фон размытым»\n"
            "• «Добавь закат на заднем плане»\n"
            "• «Преврати в мультяшный стиль»"
        ),
        reply_markup=back_keyboard(),
    )


@router.message(EditStates.waiting_image, F.document)
async def process_document_image(message: Message, state: FSMContext) -> None:
    """
    Process uploaded document (image file) for editing.
    
    Validates format and saves file_id.
    """
    document = message.document
    
    # Validate format
    if not validate_image_format(document.file_name, document.mime_type):
        await message.answer(
            text=(
                "❌ <b>Неподдерживаемый формат</b>\n\n"
                "Пожалуйста, отправьте изображение в одном из форматов:\n"
                "• JPG / JPEG\n"
                "• PNG\n"
                "• WEBP\n\n"
                "Или отправьте фото напрямую (не как файл)."
            ),
            reply_markup=back_keyboard(),
        )
        return
    
    file_id = document.file_id
    
    # Get user info
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
    
    # Save file_id to state
    await state.update_data(
        source_file_id=file_id,
        user_id=user.id,
    )
    await state.set_state(EditStates.waiting_edit_prompt)
    
    await message.answer(
        text=(
            "✅ <b>Изображение получено!</b>\n\n"
            "Теперь опишите, какие изменения вы хотите внести."
        ),
        reply_markup=back_keyboard(),
    )


@router.message(EditStates.waiting_image)
async def invalid_image_input(message: Message) -> None:
    """Handle invalid input when waiting for image."""
    await message.answer(
        text=(
            "❌ Пожалуйста, отправьте изображение.\n\n"
            "📎 <i>Поддерживаемые форматы: JPG, PNG, WEBP</i>"
        ),
        reply_markup=back_keyboard(),
    )


@router.message(EditStates.waiting_edit_prompt, F.text)
async def process_edit_prompt(message: Message, state: FSMContext) -> None:
    """
    Process the edit description/prompt.
    
    Shows cost and asks for confirmation.
    """
    prompt = message.text.strip()
    
    if not prompt:
        await message.answer(
            "❌ Пожалуйста, опишите желаемые изменения.",
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
    data = await state.get_data()
    user_id = data.get("user_id")
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        balance = user.tokens if user else 0
    
    # Save prompt to state
    await state.update_data(prompt=prompt)
    await state.set_state(EditStates.confirm_edit)
    
    # Show confirmation
    await message.answer(
        text=(
            f"✏️ <b>Подтверждение редактирования</b>\n\n"
            f"<b>Описание изменений:</b>\n<i>{prompt[:500]}{'...' if len(prompt) > 500 else ''}</i>\n\n"
            f"<b>Стоимость:</b> {EDIT_COST} 🪙\n"
            f"<b>Ваш баланс:</b> {balance} 🪙\n"
            f"<b>После редактирования:</b> {balance - EDIT_COST} 🪙\n\n"
            "Подтвердить редактирование?"
        ),
        reply_markup=confirm_keyboard(),
    )


@router.message(EditStates.waiting_edit_prompt)
async def invalid_edit_prompt_input(message: Message) -> None:
    """Handle non-text input when waiting for edit prompt."""
    await message.answer(
        "❌ Пожалуйста, отправьте текстовое описание изменений.",
        reply_markup=back_keyboard(),
    )


@router.callback_query(EditStates.confirm_edit, F.data == CallbackData.CONFIRM)
async def confirm_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Confirm and start the edit task.
    
    - Deducts tokens
    - Creates GenerationTask with type 'edit'
    - Enqueues task to RQ
    """
    data = await state.get_data()
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    source_file_id = data.get("source_file_id")
    
    if not prompt or not user_id or not source_file_id:
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
            await balance_service.deduct_tokens(user_id, EDIT_COST)
            
            # Create task with source image
            task = await task_repo.create(
                user_id=user_id,
                task_type="edit",
                prompt=prompt,
                tokens_spent=EDIT_COST,
                source_image_url=source_file_id,  # Store file_id as source
            )
            
            logger.info(f"Created edit task {task.id} for user {user_id}")
            
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
            "✅ <b>Задача создана!</b>\n\n"
            f"🆔 ID задачи: <code>{task.id}</code>\n\n"
            "⏳ Ваше изображение редактируется...\n"
            "Я отправлю результат, когда будет готово.\n\n"
            "Это может занять 10-30 секунд."
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Редактирование запущено! ⏳")


@router.callback_query(EditStates.confirm_edit, F.data == CallbackData.CANCEL)
async def cancel_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the edit and return to menu."""
    await state.clear()
    
    await callback.message.edit_text(
        text="❌ Редактирование отменено.\n\nВыберите действие:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Отменено")
