"""Handler for image editing flow."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, TaskRepository
from bot.services.balance import BalanceService, InsufficientBalanceError
from bot.services.image_tokens import (
    estimate_image_tokens,
    calculate_total_cost,
    calculate_extra_images_cost,
    is_valid_quality,
    is_valid_size,
    is_seedream_model,
    get_quality_labels_for_model,
    convert_quality_for_model,
)
from bot.keyboards.inline import (
    CallbackData,
    image_settings_confirm_keyboard,
    back_keyboard,
    main_menu_keyboard,
    insufficient_balance_keyboard,
)
from bot.states.generation import EditStates

logger = logging.getLogger(__name__)

router = Router(name="edit")


# ============== Reply-to-Edit Handler ==============
# This handler catches when user replies to a generated image with text

@router.message(F.reply_to_message.document, F.text)
async def handle_reply_to_edit(message: Message, state: FSMContext) -> None:
    """
    Handle reply to a generated image with edit prompt.
    
    When user replies to a bot's document (generated image) with text,
    start the edit flow with that image and prompt.
    """
    reply_msg = message.reply_to_message
    
    # Check if the replied message is from the bot and has a document
    if not reply_msg or not reply_msg.document:
        return
    
    # Check if it's a reply to bot's message (bot's messages have from_user as bot)
    if not reply_msg.from_user or not reply_msg.from_user.is_bot:
        return
    
    prompt = message.text.strip()
    
    if not prompt:
        await message.answer(
            "❌ Пожалуйста, напишите описание изменений.",
            reply_markup=back_keyboard(),
        )
        return
    
    if len(prompt) > 2000:
        await message.answer(
            "❌ Описание слишком длинное. Максимум 2000 символов.",
            reply_markup=back_keyboard(),
        )
        return
    
    # Get file_id from the replied document
    file_id = reply_msg.document.file_id
    
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
            return
        
        balance = user.tokens
        quality = user.image_quality
        size = user.image_size
        model = user.selected_model
    
    cost = calculate_total_cost(quality, images_count=1, model=model)
    
    # Convert quality if it doesn't match the model
    if not is_valid_quality(quality, model):
        quality = convert_quality_for_model(quality, model)
    
    # Save to state
    await state.update_data(
        source_file_id=file_id,
        source_file_ids=[file_id],
        user_id=user.id,
        prompt=prompt,
        image_quality=quality,
        image_size=size,
        model=model,
        expensive_confirmed=False,
        images_count=1,
    )
    await state.set_state(EditStates.confirm_edit)
    
    # Show confirmation
    await message.answer(
        text=_build_confirmation_text(
            prompt=prompt,
            balance=balance,
            cost=cost,
            quality=quality,
            size=size,
            model=model,
        ),
        reply_markup=image_settings_confirm_keyboard(quality, size, model=model),
    )


def _build_confirmation_text(
    prompt: str,
    balance: int,
    cost: int,
    quality: str,
    size: str,
    model: str,
    second_confirm: bool = False,
    images_count: int = 1,
) -> str:
    prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
    confirm_line = "Подтвердить редактирование ещё раз?" if second_confirm else "Подтвердить редактирование?"
    
    # Get quality label based on model
    quality_labels = get_quality_labels_for_model(model)
    quality_label = quality_labels.get(quality, quality)
    
    # Show extra cost info if multiple images
    images_info = ""
    if images_count > 1:
        extra_cost = calculate_extra_images_cost(images_count)
        if extra_cost > 0:
            images_info = f"\n<b>Изображений:</b> {images_count} (+{extra_cost} 🪙)"
        else:
            images_info = f"\n<b>Изображений:</b> {images_count}"
    
    return (
        f"🪄 <b>Подтверждение редактирования</b>\n\n"
        f"<b>Описание изменений:</b>\n<i>{prompt_preview}</i>\n\n"
        f"<b>Модель:</b> {model}\n"
        f"<b>Качество:</b> {quality_label}\n"
        f"<b>Формат:</b> {size}{images_info}\n\n"
        f"<b>Стоимость:</b> {cost} 🪙\n"
        f"<b>Ваш баланс:</b> {balance} 🪙\n"
        f"<b>После редактирования:</b> {balance - cost} 🪙\n\n"
        f"{confirm_line}"
    )

# Supported image formats
SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Maximum number of images for edit
MAX_EDIT_IMAGES = 10


def _build_photo_received_text(photos_count: int, max_photos: int = MAX_EDIT_IMAGES) -> str:
    """Build the text message when photo(s) are received."""
    header = f"✅ Фото получено! ({photos_count}/{max_photos})" if photos_count == 1 else f"✅ Получено фото: {photos_count}/{max_photos}"
    
    extra_cost_info = ""
    extra_cost = calculate_extra_images_cost(photos_count)
    if extra_cost > 0:
        extra_cost_info = f"\n💰 <i>Доп. стоимость за фото: +{extra_cost} 🪙</i>\n"
    
    return (
        f"{header}\n\n"
        "Опишите, что нужно сделать с изображением.\n\n"
        "💡 <b>Примеры:</b>\n"
        "• «Сделай портрет в студийном свете»\n"
        "• «Замени фон на город ночью с неоновыми огнями»\n"
        "• «Создай атмосферу как в кино: мягкий свет, глубина резкости»\n\n"
        "💡 <b>Если вы загрузили несколько фото, вы можете:</b>\n"
        "• «Соедини человека с первого фото с локацией со второго»\n"
        "• «Собери одно изображение, используя лучшие детали из всех фото»\n"
        "• «Возьми стиль освещения с одного снимка и примени к другому»\n"
        f"{extra_cost_info}\n"
        f"📎 Можете добавить ещё фото (до {max_photos}) или отправьте описание"
    )


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
    
    Supports multiple photos (up to 10). Each additional photo adds +10% to cost.
    Handles batch uploads (multiple photos in one message via media_group_id).
    """
    import asyncio
    import time
    
    # Get the largest photo size
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id
    current_media_group_id = message.media_group_id
    
    # Get current state data
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    
    # Check if we've reached the limit
    if len(source_file_ids) >= MAX_EDIT_IMAGES:
        return  # Silently ignore
    
    # Get user info (only on first photo)
    if not source_file_ids:
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
        
        await state.update_data(user_id=user.id)
    
    # Add photo to list with timestamp
    source_file_ids.append(file_id)
    current_time = time.time()
    
    # Update state
    await state.update_data(
        source_file_ids=source_file_ids,
        last_photo_time=current_time,
        current_media_group_id=current_media_group_id,
    )
    
    # For backward compatibility
    if len(source_file_ids) == 1:
        await state.update_data(source_file_id=file_id)
    
    await state.set_state(EditStates.waiting_edit_prompt)
    
    # Wait for more photos (debounce)
    await asyncio.sleep(1.0)
    
    # Re-read state - check if more photos arrived
    data = await state.get_data()
    last_photo_time = data.get("last_photo_time", 0)
    
    # Only send message if no new photos arrived during wait
    if last_photo_time != current_time:
        return  # Another photo arrived, let that handler send the message
    
    source_file_ids = data.get("source_file_ids", [])
    photos_count = len(source_file_ids)
    
    await message.answer(
        text=_build_photo_received_text(photos_count),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


@router.message(EditStates.waiting_image, F.document)
async def process_document_image(message: Message, state: FSMContext) -> None:
    """
    Process uploaded document (image file) for editing.
    
    Validates format and saves file_id. Supports multiple images.
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
            parse_mode="HTML",
        )
        return
    
    file_id = document.file_id
    
    # Get current state data
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    
    # Check if we've reached the limit
    if len(source_file_ids) >= MAX_EDIT_IMAGES:
        await message.answer(
            f"❌ Максимум {MAX_EDIT_IMAGES} изображений.\n\n"
            "Отправьте описание изменений.",
            reply_markup=back_keyboard(),
        )
        return
    
    # Get user info (only on first image)
    if not source_file_ids:
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
        
        await state.update_data(user_id=user.id)
    
    # Add file to list
    source_file_ids.append(file_id)
    await state.update_data(source_file_ids=source_file_ids)
    
    # For backward compatibility
    if len(source_file_ids) == 1:
        await state.update_data(source_file_id=file_id)
    
    photos_count = len(source_file_ids)
    
    await state.set_state(EditStates.waiting_edit_prompt)
    
    await message.answer(
        text=_build_photo_received_text(photos_count),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
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
    source_file_ids = data.get("source_file_ids", [])
    
    # Fallback to single file_id for backward compatibility
    if not source_file_ids:
        source_file_id = data.get("source_file_id")
        if source_file_id:
            source_file_ids = [source_file_id]
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user is None:
            await message.answer(
                "❌ Пользователь не найден. Используйте /start",
                reply_markup=back_keyboard(),
            )
            await state.clear()
            return

        balance = user.tokens
        quality = user.image_quality
        size = user.image_size
        model = user.selected_model

    # Calculate cost with new token system
    images_count = len(source_file_ids)
    cost = calculate_total_cost(quality, images_count, model=model)
    
    # Convert quality if it doesn't match the model
    if not is_valid_quality(quality, model):
        quality = convert_quality_for_model(quality, model)

    # Save prompt to state
    await state.update_data(
        prompt=prompt,
        image_quality=quality,
        image_size=size,
        model=model,
        expensive_confirmed=False,
        source_file_ids=source_file_ids,
        images_count=images_count,
    )
    await state.set_state(EditStates.confirm_edit)
    
    # Show confirmation
    await message.answer(
        text=_build_confirmation_text(
            prompt=prompt,
            balance=balance,
            cost=cost,
            quality=quality,
            size=size,
            model=model,
            images_count=images_count,
        ),
        reply_markup=image_settings_confirm_keyboard(quality, size, model=model),
    )


@router.message(EditStates.waiting_edit_prompt, F.photo)
async def process_additional_photo(message: Message, state: FSMContext) -> None:
    """Handle additional photo uploads while waiting for prompt."""
    import asyncio
    import time
    
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id
    
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    
    if len(source_file_ids) >= MAX_EDIT_IMAGES:
        return  # Silently ignore extra photos
    
    source_file_ids.append(file_id)
    current_time = time.time()
    
    # Update state with timestamp
    await state.update_data(
        source_file_ids=source_file_ids,
        last_photo_time=current_time,
    )
    
    # Wait for more photos (debounce)
    await asyncio.sleep(1.0)
    
    # Re-read state - check if more photos arrived
    data = await state.get_data()
    last_photo_time = data.get("last_photo_time", 0)
    
    # Only send message if no new photos arrived during wait
    if last_photo_time != current_time:
        return  # Another photo arrived, let that handler send the message
    
    source_file_ids = data.get("source_file_ids", [])
    photos_count = len(source_file_ids)
    extra_cost = calculate_extra_images_cost(photos_count)
    
    if extra_cost > 0:
        text = (
            f"✅ <b>Добавлено фото!</b> ({photos_count}/{MAX_EDIT_IMAGES})\n\n"
            f"💰 <i>Доп. стоимость: +{extra_cost} 🪙</i>\n\n"
            "Отправьте описание изменений или добавьте ещё фото."
        )
    else:
        text = (
            f"✅ <b>Добавлено фото!</b> ({photos_count}/{MAX_EDIT_IMAGES})\n\n"
            "Отправьте описание изменений или добавьте ещё фото."
        )
    
    await message.answer(
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


@router.message(EditStates.waiting_edit_prompt, F.document)
async def process_additional_document(message: Message, state: FSMContext) -> None:
    """Handle additional document uploads while waiting for prompt."""
    document = message.document
    
    if not validate_image_format(document.file_name, document.mime_type):
        await message.answer(
            "❌ Неподдерживаемый формат. Используйте JPG, PNG или WEBP.",
            reply_markup=back_keyboard(),
        )
        return
    
    file_id = document.file_id
    
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    
    if len(source_file_ids) >= MAX_EDIT_IMAGES:
        await message.answer(
            f"❌ Максимум {MAX_EDIT_IMAGES} изображений.\n\n"
            "Отправьте описание изменений.",
            reply_markup=back_keyboard(),
        )
        return
    
    source_file_ids.append(file_id)
    await state.update_data(source_file_ids=source_file_ids)
    
    photos_count = len(source_file_ids)
    extra_cost = calculate_extra_images_cost(photos_count)
    
    if extra_cost > 0:
        text = (
            f"✅ <b>Изображение добавлено!</b> ({photos_count}/{MAX_EDIT_IMAGES})\n\n"
            f"💰 <i>Доп. стоимость: +{extra_cost} 🪙</i>\n\n"
            "Отправьте описание изменений или добавьте ещё фото."
        )
    else:
        text = (
            f"✅ <b>Изображение добавлено!</b> ({photos_count}/{MAX_EDIT_IMAGES})\n\n"
            "Отправьте описание изменений или добавьте ещё фото."
        )
    
    await message.answer(
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(
    EditStates.confirm_edit,
    F.data.startswith(CallbackData.IMAGE_QUALITY_PREFIX),
)
async def set_edit_quality(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quality selection while confirming edit."""

    value = callback.data.replace(CallbackData.IMAGE_QUALITY_PREFIX, "")
    
    data = await state.get_data()
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    size = data.get("image_size")
    model = data.get("model")

    if not prompt or not user_id or not size or not model:
        await callback.answer("❌ Ошибка состояния")
        await state.clear()
        return

    # Validate quality for the current model
    if not is_valid_quality(value, model):
        await callback.answer("❌ Неверное качество")
        return

    await state.update_data(image_quality=value, expensive_confirmed=False)

    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_image_settings(user_id=user_id, image_quality=value)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        balance = user.tokens if user else 0

    # Get images count from state
    data = await state.get_data()
    images_count = data.get("images_count", 1)
    cost = calculate_total_cost(value, images_count, model=model)
    
    await callback.message.edit_text(
        text=_build_confirmation_text(
            prompt=prompt,
            balance=balance,
            cost=cost,
            quality=value,
            size=size,
            model=model,
            images_count=images_count,
        ),
        reply_markup=image_settings_confirm_keyboard(value, size, model=model),
    )
    await callback.answer()


@router.callback_query(
    EditStates.confirm_edit,
    F.data.startswith(CallbackData.IMAGE_SIZE_PREFIX),
)
async def set_edit_size(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle size selection while confirming edit."""

    value = callback.data.replace(CallbackData.IMAGE_SIZE_PREFIX, "")
    if not is_valid_size(value):
        await callback.answer("❌ Неверный формат")
        return

    data = await state.get_data()
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    quality = data.get("image_quality")
    model = data.get("model")

    if not prompt or not user_id or not quality or not model:
        await callback.answer("❌ Ошибка состояния")
        await state.clear()
        return

    await state.update_data(image_size=value, expensive_confirmed=False)

    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_image_settings(user_id=user_id, image_size=value)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        balance = user.tokens if user else 0

    images_count = data.get("images_count", 1)
    cost = calculate_total_cost(quality, images_count, model=model)
    
    await callback.message.edit_text(
        text=_build_confirmation_text(
            prompt=prompt,
            balance=balance,
            cost=cost,
            quality=quality,
            size=value,
            model=model,
            images_count=images_count,
        ),
        reply_markup=image_settings_confirm_keyboard(quality, value, model=model),
    )
    await callback.answer()


@router.message(EditStates.waiting_edit_prompt)
async def invalid_edit_prompt_input(message: Message) -> None:
    """Handle invalid input when waiting for edit prompt."""
    await message.answer(
        "❌ Пожалуйста, отправьте текстовое описание изменений или добавьте ещё фото.",
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
    source_file_ids = data.get("source_file_ids", [])
    quality = data.get("image_quality")
    size = data.get("image_size")
    model = data.get("model")
    expensive_confirmed = data.get("expensive_confirmed", False)
    
    # Use first image for the task (OpenAI edit supports one image)
    if not source_file_id and source_file_ids:
        source_file_id = source_file_ids[0]
    
    if not prompt or not user_id or not source_file_id or not quality or not size or not model:
        await callback.message.edit_text(
            "❌ Ошибка: данные сессии потеряны. Попробуйте снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return

    # Calculate cost with new token system
    images_count = len(source_file_ids) if source_file_ids else 1
    cost = calculate_total_cost(quality, images_count, model=model)

    if cost >= config.high_cost_threshold and not expensive_confirmed:
        session_maker = get_session_maker()
        async with session_maker() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(callback.from_user.id)
            balance = user.tokens if user else 0

        await state.update_data(expensive_confirmed=True)
        await callback.message.edit_text(
            text=_build_confirmation_text(
                prompt=prompt,
                balance=balance,
                cost=cost,
                quality=quality,
                size=size,
                model=model,
                second_confirm=True,
                images_count=images_count,
            ),
            reply_markup=image_settings_confirm_keyboard(
                quality,
                size,
                confirm_callback_data=CallbackData.EXPENSIVE_CONFIRM,
                model=model,
            ),
        )
        await callback.answer("Подтвердите ещё раз")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        balance_service = BalanceService(session)
        task_repo = TaskRepository(session)
        
        try:
            # Deduct tokens
            await balance_service.deduct_tokens(user_id, cost)
            
            # Create task with source image (store all file_ids as JSON if multiple)
            source_data = source_file_id
            if source_file_ids and len(source_file_ids) > 1:
                import json
                source_data = json.dumps(source_file_ids)
            
            task = await task_repo.create(
                user_id=user_id,
                task_type="edit",
                prompt=prompt,
                tokens_spent=cost,
                model=model,
                image_quality=quality,
                image_size=size,
                source_image_url=source_data,
                images_count=images_count,
            )
            
            logger.info(f"Created edit task {task.id} for user {user_id}")
            
        except InsufficientBalanceError as e:
            await callback.message.edit_text(
                text=(
                    "Ой! Кажется, токены закончились 📸\n\n"
                    f"Требуется: {e.required} 🪙\n"
                    f"Ваш баланс: {e.available} 🪙\n\n"
                    "Пополни баланс в магазине, чтобы продолжить! 👾"
                ),
                reply_markup=insufficient_balance_keyboard(),
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
            "⏳ Ваше изображение редактируется...\n"
            "Я отправлю результат, когда будет готово.\n\n"
            "Это может занять 10-30 секунд."
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Редактирование запущено! ⏳")


@router.callback_query(
    EditStates.confirm_edit,
    F.data == CallbackData.EXPENSIVE_CONFIRM,
)
async def confirm_edit_expensive(callback: CallbackQuery, state: FSMContext) -> None:
    """Second step confirmation for expensive edit."""

    data = await state.get_data()
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    source_file_id = data.get("source_file_id")
    source_file_ids = data.get("source_file_ids", [])
    quality = data.get("image_quality")
    size = data.get("image_size")
    model = data.get("model")

    # Use first image for the task
    if not source_file_id and source_file_ids:
        source_file_id = source_file_ids[0]

    if not prompt or not user_id or not source_file_id or not quality or not size or not model:
        await callback.message.edit_text(
            "❌ Ошибка: данные сессии потеряны. Попробуйте снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return

    # Calculate cost with new token system
    images_count = len(source_file_ids) if source_file_ids else 1
    cost = calculate_total_cost(quality, images_count)

    session_maker = get_session_maker()
    async with session_maker() as session:
        balance_service = BalanceService(session)
        task_repo = TaskRepository(session)

        try:
            await balance_service.deduct_tokens(user_id, cost)

            # Store all file_ids as JSON if multiple
            source_data = source_file_id
            if source_file_ids and len(source_file_ids) > 1:
                import json
                source_data = json.dumps(source_file_ids)

            task = await task_repo.create(
                user_id=user_id,
                task_type="edit",
                prompt=prompt,
                tokens_spent=cost,
                model=model,
                image_quality=quality,
                image_size=size,
                source_image_url=source_data,
                images_count=images_count,
            )

            logger.info(f"Created edit task {task.id} for user {user_id}")

        except InsufficientBalanceError as e:
            await callback.message.edit_text(
                text=(
                    "Ой! Кажется, токены закончились 📸\n\n"
                    f"Требуется: {e.required} 🪙\n"
                    f"Ваш баланс: {e.available} 🪙\n\n"
                    "Пополни баланс в магазине, чтобы продолжить! 👾"
                ),
                reply_markup=insufficient_balance_keyboard(),
            )
            await state.clear()
            await callback.answer()
            return

    await state.clear()

    try:
        from bot.tasks.generation import enqueue_generation_task
        enqueue_generation_task(task.id)
    except Exception as e:
        logger.error(f"Failed to enqueue task {task.id}: {e}")

    await callback.message.edit_text(
        text=(
            "✅ <b>Задача создана!</b>\n\n"
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
