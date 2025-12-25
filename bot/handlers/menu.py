"""Handler for main menu navigation."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import (
    CallbackData,
    main_menu_keyboard,
    model_keyboard,
    tokens_keyboard,
    templates_keyboard,
    back_keyboard,
)
from bot.states.generation import GenerationStates, EditStates
from bot.db.database import get_session_maker
from bot.db.repositories import UserRepository

logger = logging.getLogger(__name__)

router = Router(name="menu")


MENU_MESSAGE = """
🎨 <b>Главное меню</b>

Выберите действие:
"""


@router.callback_query(F.data == CallbackData.BACK_TO_MENU)
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle back to menu button - return to main menu."""
    # Clear any FSM state
    await state.clear()
    
    await callback.message.edit_text(
        text=MENU_MESSAGE,
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == CallbackData.GENERATE)
async def menu_generate(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Создать картинку' button."""
    await state.set_state(GenerationStates.waiting_prompt)
    
    await callback.message.edit_text(
        text=(
            "🎨 <b>Создание картинки</b>\n\n"
            "Опишите, какое изображение вы хотите создать.\n\n"
            "💡 <i>Совет: чем подробнее описание, тем лучше результат!</i>"
        ),
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == CallbackData.EDIT)
async def menu_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Редактировать фото' button."""
    await state.set_state(EditStates.waiting_image)
    
    await callback.message.edit_text(
        text=(
            "✏️ <b>Редактирование фото</b>\n\n"
            "Отправьте изображение, которое хотите отредактировать.\n\n"
            "📎 <i>Поддерживаемые форматы: JPG, PNG, WEBP</i>"
        ),
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == CallbackData.MODEL)
async def menu_model(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Выбрать модель' button."""
    await state.clear()
    
    # Get user's current model
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        current_model = user.selected_model if user else "gpt-image-1"
    
    model_names = {
        "gpt-image-1": "GPT-Image-1 (Стандартная)",
        "gpt-image-1.5": "GPT-Image-1.5 (Улучшенная)",
    }
    model_name = model_names.get(current_model, current_model)
    
    await callback.message.edit_text(
        text=(
            "🤖 <b>Выбор модели</b>\n\n"
            f"Текущая модель: <b>{model_name}</b>\n\n"
            "Выберите модель для генерации изображений:"
        ),
        reply_markup=model_keyboard(current_model),
    )
    await callback.answer()


@router.callback_query(F.data == CallbackData.PROFILE)
async def menu_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Личный кабинет' button - redirects to profile handler."""
    # This will be handled by profile.py router
    # Just answer the callback to prevent timeout
    await callback.answer()


@router.callback_query(F.data == CallbackData.TOKENS)
async def menu_tokens(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Купить токены' button."""
    await state.clear()
    
    # Get current balance
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        balance = user.tokens if user else 0
    
    await callback.message.edit_text(
        text=(
            "💰 <b>Купить токены</b>\n\n"
            f"Ваш текущий баланс: <b>{balance}</b> 🪙\n\n"
            "Пакеты токенов:\n"
            "• 50 токенов — 99 ₽\n"
            "• 150 токенов — 249 ₽\n"
            "• 500 токенов — 699 ₽\n\n"
            "🔜 <i>Оплата скоро будет доступна</i>"
        ),
        reply_markup=tokens_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == CallbackData.TRENDS)
async def menu_trends(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Идеи и тренды' button."""
    await state.clear()
    
    await callback.message.edit_text(
        text=(
            "💡 <b>Идеи и тренды</b>\n\n"
            "Выберите готовый шаблон для быстрой генерации:\n\n"
            "Каждый шаблон содержит оптимизированный промпт "
            "для создания качественного изображения."
        ),
        reply_markup=templates_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == CallbackData.GUIDE)
async def menu_guide(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Гайд' button - redirects to guide handler."""
    # This will be handled by guide.py router
    await callback.answer()


# Handle placeholder buttons
@router.callback_query(F.data == "tokens:coming_soon")
async def tokens_coming_soon(callback: CallbackQuery) -> None:
    """Handle 'coming soon' tokens button."""
    await callback.answer(
        "Оплата скоро будет доступна! 💳",
        show_alert=True,
    )
