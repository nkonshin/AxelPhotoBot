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
from bot.utils.messages import (
    MENU_MESSAGE,
    LOW_BALANCE_WARNING,
    SHOP_MESSAGE,
    GENERATE_PROMPT_REQUEST,
    EDIT_IMAGE_REQUEST,
    MODEL_SELECTION,
    MODEL_DISABLED,
    TRENDS_MENU,
)

logger = logging.getLogger(__name__)

router = Router(name="menu")


@router.callback_query(F.data == CallbackData.BACK_TO_MENU)
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle back to menu button - return to main menu."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    # Clear any FSM state
    await state.clear()
    
    # Get user info for personalized message
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        balance = user.tokens if user else 0
    
    user_name = user_tg.first_name or user_tg.username or "друг"
    max_generations = balance // 2  # Low quality = 2 tokens
    
    # Show low balance warning if 3 or fewer tokens
    low_balance_warning = LOW_BALANCE_WARNING if balance <= 3 else ""
    
    await callback.message.edit_text(
        text=MENU_MESSAGE.format(
            user_name=user_name,
            balance=balance,
            max_generations=max_generations,
            low_balance_warning=low_balance_warning,
        ),
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == CallbackData.GENERATE)
async def menu_generate(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Создать картинку с нуля' button."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    await state.set_state(GenerationStates.waiting_prompt)
    
    await callback.message.edit_text(
        text=GENERATE_PROMPT_REQUEST,
        reply_markup=back_keyboard(),
    )


@router.callback_query(F.data == CallbackData.EDIT)
async def menu_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Редактировать твоё фото' button."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    await state.set_state(EditStates.waiting_image)
    
    await callback.message.edit_text(
        text=EDIT_IMAGE_REQUEST,
        reply_markup=back_keyboard(),
    )


@router.callback_query(F.data == CallbackData.MODEL)
async def menu_model(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Выбрать модель' button."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    await state.clear()
    
    # Get user's current model
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        current_model = user.selected_model if user else "gpt-image-1"
    
    model_names = {
        "gpt-image-1": "GPT Image 1 (Стандартная)",
        "gpt-image-1.5": "GPT Image 1.5 (Улучшенная)",
    }
    model_name = model_names.get(current_model, current_model)
    
    await callback.message.edit_text(
        text=MODEL_SELECTION.format(model_name=model_name),
        reply_markup=model_keyboard(current_model),
    )


@router.callback_query(F.data == CallbackData.TOKENS)
async def menu_tokens(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Купить токены' button - show shop."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    await state.clear()
    
    # Get current balance
    user_tg = callback.from_user
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_tg.id)
        balance = user.tokens if user else 0
    
    await callback.message.edit_text(
        text=SHOP_MESSAGE.format(balance=balance),
        reply_markup=tokens_keyboard(),
    )


@router.callback_query(F.data == CallbackData.TRENDS)
async def menu_trends(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Идеи и тренды' button."""
    # Answer callback immediately to prevent timeout
    await callback.answer()
    
    await state.clear()
    
    await callback.message.edit_text(
        text=TRENDS_MENU,
        reply_markup=templates_keyboard(),
    )


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


# Handle disabled model selection
@router.callback_query(F.data == "model:disabled")
async def model_disabled(callback: CallbackQuery) -> None:
    """Handle disabled model button (GPT Image 1)."""
    await callback.answer(
        MODEL_DISABLED,
        show_alert=True,
    )
