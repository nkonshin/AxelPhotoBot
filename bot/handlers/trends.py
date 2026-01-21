"""Handler for Ideas and Trends (Идеи и тренды) - Edit templates."""

import logging
import asyncio
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository, TaskRepository
from bot.services.balance import BalanceService, InsufficientBalanceError
from bot.services.image_tokens import (
    calculate_total_cost,
    calculate_extra_images_cost,
    is_valid_quality,
    is_valid_size,
    is_seedream_model,
    get_quality_labels_for_model,
    convert_quality_for_model,
    get_actual_resolution,
)
from bot.templates.edit_templates import get_edit_template_by_id, get_all_edit_templates
from bot.keyboards.inline import (
    CallbackData,
    image_settings_confirm_keyboard,
    back_keyboard,
    main_menu_keyboard,
    insufficient_balance_keyboard,
    templates_keyboard,
    template_photos_keyboard,
)
from bot.states.generation import TemplateEditStates

logger = logging.getLogger(__name__)

router = Router(name="trends")


# Maximum number of images for edit
MAX_EDIT_IMAGES = 10

# Supported image formats
SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_format(file_name: str | None, mime_type: str | None) -> bool:
    """Validate that the image format is supported."""
    if mime_type and mime_type.lower() in SUPPORTED_FORMATS:
        return True
    if file_name:
        file_name_lower = file_name.lower()
        for ext in SUPPORTED_EXTENSIONS:
            if file_name_lower.endswith(ext):
                return True
    return False


def _build_template_confirmation_text(
    template_name: str,
    prompt: str,
    balance: int,
    cost: int,
    quality: str,
    size: str,
    model: str,
    images_count: int = 1,
    second_confirm: bool = False,
) -> str:
    """Build confirmation text for template edit."""
    prompt_preview = prompt[:400] + "..." if len(prompt) > 400 else prompt
    confirm_line = "Подтвердить редактирование ещё раз?" if second_confirm else "Подтвердить редактирование?"
    
    quality_labels = get_quality_labels_for_model(model)
    quality_label = quality_labels.get(quality, quality)
    actual_resolution = get_actual_resolution(model, quality, size)
    
    images_info = ""
    if images_count > 1:
        extra_cost = calculate_extra_images_cost(images_count)
        if extra_cost > 0:
            images_info = f"\n<b>Изображений:</b> {images_count} (+{extra_cost} 🪙)"
        else:
            images_info = f"\n<b>Изображений:</b> {images_count}"
    
    return (
        f"💡 <b>{template_name}</b>\n\n"
        f"<b>Промпт:</b>\n<i>{prompt_preview}</i>\n\n"
        f"<b>Модель:</b> {model}\n"
        f"<b>Качество:</b> {quality_label}\n"
        f"<b>Формат:</b> {actual_resolution}{images_info}\n\n"
        f"<b>Стоимость:</b> {cost} 🪙\n"
        f"<b>Ваш баланс:</b> {balance} 🪙\n"
        f"<b>После редактирования:</b> {balance - cost} 🪙\n\n"
        f"{confirm_line}"
    )


# =============================================================================
# TEMPLATE SELECTION - User clicks on a template button
# =============================================================================

@router.callback_query(F.data.startswith(CallbackData.EDIT_TEMPLATE_PREFIX))
async def select_edit_template(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle edit template selection - ask user to upload photo."""
    template_id = callback.data.replace(CallbackData.EDIT_TEMPLATE_PREFIX, "")
    
    template = get_edit_template_by_id(template_id)
    if template is None:
        await callback.answer("❌ Шаблон не найден")
        return
    
    # Get user info
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
    
    # Save template to state and wait for photo
    await state.update_data(
        template_id=template_id,
        template_name=template.name,
        template_prompt=template.prompt,
        user_id=user.id,
        source_file_ids=[],
    )
    await state.set_state(TemplateEditStates.waiting_photos)
    
    await callback.message.edit_text(
        text=(
            f"💡 <b>{template.name}</b>\n\n"
            f"<b>Описание:</b> {template.description}\n\n"
            f"📸 <b>Отправьте фото</b> для редактирования.\n\n"
            f"Можно отправить до {MAX_EDIT_IMAGES} фото.\n"
            f"После загрузки нажмите кнопку <b>«Готово»</b>."
        ),
        reply_markup=back_keyboard(),
    )
    await callback.answer()


# =============================================================================
# PHOTO UPLOAD HANDLERS
# =============================================================================

@router.message(TemplateEditStates.waiting_photos, F.photo)
async def process_template_photo(message: Message, state: FSMContext) -> None:
    """Process uploaded photo for template editing."""
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id
    
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    template_name = data.get("template_name", "Шаблон")
    
    if len(source_file_ids) >= MAX_EDIT_IMAGES:
        await message.answer(
            f"❌ Максимум {MAX_EDIT_IMAGES} фото. Нажмите «Готово» для продолжения.",
            reply_markup=template_photos_keyboard(len(source_file_ids)),
        )
        return
    
    source_file_ids.append(file_id)
    current_time = time.time()
    
    await state.update_data(
        source_file_ids=source_file_ids,
        source_file_id=file_id if len(source_file_ids) == 1 else data.get("source_file_id"),
        last_photo_time=current_time,
    )
    
    # Wait for more photos (debounce for batch uploads)
    await asyncio.sleep(1.0)
    
    # Re-read state
    data = await state.get_data()
    last_photo_time = data.get("last_photo_time", 0)
    
    if last_photo_time != current_time:
        return  # Another photo arrived
    
    source_file_ids = data.get("source_file_ids", [])
    photos_count = len(source_file_ids)
    
    await message.answer(
        text=(
            f"✅ <b>Получено фото: {photos_count}</b>\n\n"
            f"📎 Можете добавить ещё (до {MAX_EDIT_IMAGES}) или нажмите <b>«Готово»</b>"
        ),
        reply_markup=template_photos_keyboard(photos_count),
        parse_mode="HTML",
    )


@router.message(TemplateEditStates.waiting_photos, F.document)
async def process_template_document(message: Message, state: FSMContext) -> None:
    """Process uploaded document for template editing."""
    document = message.document
    
    if not validate_image_format(document.file_name, document.mime_type):
        await message.answer(
            "❌ Неподдерживаемый формат. Используйте JPG, PNG или WEBP.",
            reply_markup=back_keyboard(),
        )
        return
    
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    
    if len(source_file_ids) >= MAX_EDIT_IMAGES:
        await message.answer(
            f"❌ Максимум {MAX_EDIT_IMAGES} фото. Нажмите «Готово» для продолжения.",
            reply_markup=template_photos_keyboard(len(source_file_ids)),
        )
        return
    
    source_file_ids.append(document.file_id)
    
    await state.update_data(
        source_file_ids=source_file_ids,
        source_file_id=document.file_id if len(source_file_ids) == 1 else data.get("source_file_id"),
    )
    
    photos_count = len(source_file_ids)
    
    await message.answer(
        text=(
            f"✅ <b>Получено фото: {photos_count}</b>\n\n"
            f"📎 Можете добавить ещё (до {MAX_EDIT_IMAGES}) или нажмите <b>«Готово»</b>"
        ),
        reply_markup=template_photos_keyboard(photos_count),
        parse_mode="HTML",
    )


@router.message(TemplateEditStates.waiting_photos)
async def invalid_template_photo_input(message: Message, state: FSMContext) -> None:
    """Handle invalid input when waiting for photos."""
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    
    if source_file_ids:
        await message.answer(
            f"📸 У вас уже {len(source_file_ids)} фото. Добавьте ещё или нажмите «Готово».",
            reply_markup=template_photos_keyboard(len(source_file_ids)),
        )
    else:
        await message.answer(
            "❌ Пожалуйста, отправьте фото для редактирования.",
            reply_markup=back_keyboard(),
        )


# =============================================================================
# PHOTOS READY - User clicks "Готово" button
# =============================================================================

@router.callback_query(TemplateEditStates.waiting_photos, F.data == CallbackData.TEMPLATE_PHOTOS_READY)
async def photos_ready(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Photos ready' button - show confirmation screen."""
    data = await state.get_data()
    source_file_ids = data.get("source_file_ids", [])
    template_name = data.get("template_name")
    template_prompt = data.get("template_prompt")
    user_id = data.get("user_id")
    
    if not source_file_ids:
        await callback.answer("❌ Сначала загрузите хотя бы одно фото")
        return
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        
        if user is None:
            await callback.message.edit_text(
                "❌ Пользователь не найден.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            await callback.answer()
            return
        
        balance = user.tokens
        quality = user.image_quality
        size = user.image_size
        model = user.selected_model
    
    # Convert quality if needed
    if not is_valid_quality(quality, model):
        quality = convert_quality_for_model(quality, model)
    
    images_count = len(source_file_ids)
    cost = calculate_total_cost(quality, images_count, model=model)
    
    await state.update_data(
        prompt=template_prompt,
        image_quality=quality,
        image_size=size,
        model=model,
        images_count=images_count,
        expensive_confirmed=False,
    )
    await state.set_state(TemplateEditStates.confirm_edit)
    
    await callback.message.edit_text(
        text=_build_template_confirmation_text(
            template_name=template_name,
            prompt=template_prompt,
            balance=balance,
            cost=cost,
            quality=quality,
            size=size,
            model=model,
            images_count=images_count,
        ),
        reply_markup=image_settings_confirm_keyboard(quality, size, model=model),
    )
    await callback.answer()


# =============================================================================
# SETTINGS HANDLERS (Quality/Size selection)
# =============================================================================

@router.callback_query(
    TemplateEditStates.confirm_edit,
    F.data.startswith(CallbackData.IMAGE_QUALITY_PREFIX),
)
async def set_template_edit_quality(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quality selection for template edit."""
    value = callback.data.replace(CallbackData.IMAGE_QUALITY_PREFIX, "")
    
    data = await state.get_data()
    template_name = data.get("template_name")
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    size = data.get("image_size")
    model = data.get("model")
    current_quality = data.get("image_quality")
    images_count = data.get("images_count", 1)
    
    if not prompt or not user_id or not size or not model:
        await callback.answer("❌ Ошибка состояния")
        await state.clear()
        return
    
    if not is_valid_quality(value, model):
        await callback.answer("❌ Неверное качество")
        return
    
    if value == current_quality:
        await callback.answer("✅ Уже выбрано")
        return
    
    await state.update_data(image_quality=value, expensive_confirmed=False)
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_image_settings(user_id=user_id, image_quality=value)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        balance = user.tokens if user else 0
    
    cost = calculate_total_cost(value, images_count, model=model)
    
    await callback.message.edit_text(
        text=_build_template_confirmation_text(
            template_name=template_name,
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
    TemplateEditStates.confirm_edit,
    F.data.startswith(CallbackData.IMAGE_SIZE_PREFIX),
)
async def set_template_edit_size(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle size selection for template edit."""
    value = callback.data.replace(CallbackData.IMAGE_SIZE_PREFIX, "")
    
    if not is_valid_size(value):
        await callback.answer("❌ Неверный формат")
        return
    
    data = await state.get_data()
    template_name = data.get("template_name")
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    quality = data.get("image_quality")
    model = data.get("model")
    current_size = data.get("image_size")
    images_count = data.get("images_count", 1)
    
    if not prompt or not user_id or not quality or not model:
        await callback.answer("❌ Ошибка состояния")
        await state.clear()
        return
    
    if value == current_size:
        await callback.answer("✅ Уже выбрано")
        return
    
    await state.update_data(image_size=value, expensive_confirmed=False)
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_image_settings(user_id=user_id, image_size=value)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        balance = user.tokens if user else 0
    
    cost = calculate_total_cost(quality, images_count, model=model)
    
    await callback.message.edit_text(
        text=_build_template_confirmation_text(
            template_name=template_name,
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


# =============================================================================
# CONFIRMATION HANDLERS
# =============================================================================

@router.callback_query(TemplateEditStates.confirm_edit, F.data == CallbackData.CONFIRM)
async def confirm_template_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Confirm and start template edit task."""
    data = await state.get_data()
    template_name = data.get("template_name")
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    source_file_id = data.get("source_file_id")
    source_file_ids = data.get("source_file_ids", [])
    quality = data.get("image_quality")
    size = data.get("image_size")
    model = data.get("model")
    expensive_confirmed = data.get("expensive_confirmed", False)
    images_count = data.get("images_count", 1)
    
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
    
    cost = calculate_total_cost(quality, images_count, model=model)
    
    if cost >= config.high_cost_threshold and not expensive_confirmed:
        session_maker = get_session_maker()
        async with session_maker() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(callback.from_user.id)
            balance = user.tokens if user else 0
        
        await state.update_data(expensive_confirmed=True)
        await callback.message.edit_text(
            text=_build_template_confirmation_text(
                template_name=template_name,
                prompt=prompt,
                balance=balance,
                cost=cost,
                quality=quality,
                size=size,
                model=model,
                images_count=images_count,
                second_confirm=True,
            ),
            reply_markup=image_settings_confirm_keyboard(
                quality, size,
                confirm_callback_data=CallbackData.EXPENSIVE_CONFIRM,
                model=model,
            ),
        )
        await callback.answer("Подтвердите ещё раз")
        return
    
    await _execute_template_edit(callback, state, data, cost)


@router.callback_query(TemplateEditStates.confirm_edit, F.data == CallbackData.EXPENSIVE_CONFIRM)
async def confirm_template_edit_expensive(callback: CallbackQuery, state: FSMContext) -> None:
    """Second confirmation for expensive template edit."""
    data = await state.get_data()
    images_count = data.get("images_count", 1)
    quality = data.get("image_quality")
    cost = calculate_total_cost(quality, images_count, model=data.get("model"))
    
    await _execute_template_edit(callback, state, data, cost)


async def _execute_template_edit(
    callback: CallbackQuery,
    state: FSMContext,
    data: dict,
    cost: int,
) -> None:
    """Execute the template edit task."""
    template_name = data.get("template_name")
    prompt = data.get("prompt")
    user_id = data.get("user_id")
    source_file_id = data.get("source_file_id")
    source_file_ids = data.get("source_file_ids", [])
    quality = data.get("image_quality")
    size = data.get("image_size")
    model = data.get("model")
    images_count = data.get("images_count", 1)
    
    if not source_file_id and source_file_ids:
        source_file_id = source_file_ids[0]
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        balance_service = BalanceService(session)
        task_repo = TaskRepository(session)
        
        try:
            await balance_service.deduct_tokens(user_id, cost)
            
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
            
            logger.info(f"Created template edit task {task.id} for user {user_id}")
            
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
    
    # Start progress animation immediately
    from bot.utils.progress_animation import ProgressAnimator
    from bot.config import config
    
    progress_animator = ProgressAnimator(
        telegram_id=callback.from_user.id,
        bot_token=config.bot_token,
        task_type="edit",
        total_steps=5,
    )
    await progress_animator.start()
    
    try:
        from bot.tasks.generation import enqueue_generation_task
        enqueue_generation_task(task.id)
    except Exception as e:
        logger.error(f"Failed to enqueue task {task.id}: {e}")
    
    # Delete confirmation message
    await callback.message.delete()
    await callback.answer("Редактирование запущено! ⏳")


# =============================================================================
# CANCEL HANDLER
# =============================================================================

@router.callback_query(TemplateEditStates.confirm_edit, F.data == CallbackData.CANCEL)
async def cancel_template_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel template edit and return to templates list."""
    await state.clear()
    
    await callback.message.edit_text(
        text=(
            "💡 <b>Идеи и тренды</b>\n\n"
            "Выберите готовый шаблон для редактирования фото:"
        ),
        reply_markup=templates_keyboard(),
    )
    await callback.answer("Отменено")


@router.callback_query(TemplateEditStates.waiting_photos, F.data == CallbackData.BACK_TO_MENU)
async def cancel_photo_upload(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel photo upload and return to menu."""
    await state.clear()
    
    await callback.message.edit_text(
        text=(
            "💡 <b>Идеи и тренды</b>\n\n"
            "Выберите готовый шаблон для редактирования фото:"
        ),
        reply_markup=templates_keyboard(),
    )
    await callback.answer("Отменено")
