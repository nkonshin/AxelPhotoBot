"""Inline keyboards for the bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.templates.prompts import get_all_templates
from bot.services.image_tokens import (
    IMAGE_QUALITY_LABELS,
    IMAGE_SIZE_LABELS,
    ImageQuality,
    ImageSize,
)


# Callback data prefixes
class CallbackData:
    """Callback data constants."""
    
    # Main menu actions
    GENERATE = "menu:generate"
    EDIT = "menu:edit"
    MODEL = "menu:model"
    PROFILE = "menu:profile"
    TOKENS = "menu:tokens"
    TRENDS = "menu:trends"
    GUIDE = "menu:guide"
    
    # Confirmation actions
    CONFIRM = "confirm:yes"
    EXPENSIVE_CONFIRM = "confirm:expensive"
    CANCEL = "confirm:no"
    
    # Navigation
    BACK_TO_MENU = "nav:menu"
    
    # Template prefix
    TEMPLATE_PREFIX = "template:"

    # Image settings
    IMAGE_QUALITY_PREFIX = "img:quality:"
    IMAGE_SIZE_PREFIX = "img:size:"
    
    # Regenerate
    REGENERATE_PREFIX = "regen:"
    
    # Shop packages
    SHOP_STARTER = "shop:starter"
    SHOP_SMALL = "shop:small"
    SHOP_MEDIUM = "shop:medium"
    SHOP_PRO = "shop:pro"
    SHOP_VIP = "shop:vip"
    SHOP_CONTACT = "shop:contact"


# Shop packages configuration
SHOP_PACKAGES = {
    "starter": {"name": "🐣 Starter", "tokens": 10, "price": 99},
    "small": {"name": "✨ Small", "tokens": 50, "price": 249},
    "medium": {"name": "🔥 Medium", "tokens": 120, "price": 449},
    "pro": {"name": "😎 Pro", "tokens": 300, "price": 890},
    "vip": {"name": "👑 Vip", "tokens": 700, "price": 1690},
}


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Create the main menu keyboard with 6 buttons.
    
    Layout (full width buttons except middle row):
    [🎨 Создать картинку        ]
    [✏️ Редактировать фото      ]
    [🤖 Выбрать модель          ]
    [👤 Личный кабинет] [💰 Купить токены]
    [💡 Идеи и тренды           ]
    """
    builder = InlineKeyboardBuilder()
    
    # Full width buttons
    builder.row(
        InlineKeyboardButton(
            text="🎨 Создать картинку",
            callback_data=CallbackData.GENERATE,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать фото",
            callback_data=CallbackData.EDIT,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🤖 Выбрать модель",
            callback_data=CallbackData.MODEL,
        ),
    )
    # Two buttons in one row
    builder.row(
        InlineKeyboardButton(
            text="👤 Личный кабинет",
            callback_data=CallbackData.PROFILE,
        ),
        InlineKeyboardButton(
            text="💰 Купить токены",
            callback_data=CallbackData.TOKENS,
        ),
    )
    # Full width button
    builder.row(
        InlineKeyboardButton(
            text="💡 Идеи и тренды",
            callback_data=CallbackData.TRENDS,
        ),
    )
    
    return builder.as_markup()


def image_settings_confirm_keyboard(
    current_quality: ImageQuality,
    current_size: ImageSize,
    confirm_callback_data: str = CallbackData.CONFIRM,
) -> InlineKeyboardMarkup:
    """Create keyboard to select image quality/size and confirm/cancel."""

    builder = InlineKeyboardBuilder()

    # Quality row
    for quality in ("low", "medium", "high"):
        label = IMAGE_QUALITY_LABELS[quality]
        text = f"✅ {label}" if quality == current_quality else label
        builder.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{CallbackData.IMAGE_QUALITY_PREFIX}{quality}",
            )
        )
    builder.adjust(3)

    # Size row
    for size in ("1024x1024", "1024x1536", "1536x1024"):
        label = IMAGE_SIZE_LABELS[size]
        text = f"✅ {label}" if size == current_size else label
        builder.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{CallbackData.IMAGE_SIZE_PREFIX}{size}",
            )
        )
    builder.adjust(3, 3)

    # Confirm row
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=confirm_callback_data,
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=CallbackData.CANCEL,
        ),
    )

    return builder.as_markup()


def templates_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard with template options.
    
    Shows all available templates as buttons.
    """
    builder = InlineKeyboardBuilder()
    
    templates = get_all_templates()
    for template in templates:
        builder.row(
            InlineKeyboardButton(
                text=f"{template.name}",
                callback_data=f"{CallbackData.TEMPLATE_PREFIX}{template.id}",
            )
        )
    
    # Add back button
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Create confirmation keyboard.
    
    Layout:
    [✅ Подтвердить] [❌ Отмена]
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=CallbackData.CONFIRM,
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=CallbackData.CANCEL,
        ),
    )
    
    return builder.as_markup()


def back_keyboard() -> InlineKeyboardMarkup:
    """
    Create back to menu keyboard.
    
    Layout:
    [◀️ Назад в меню]
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


def model_keyboard(current_model: str = "gpt-image-1.5") -> InlineKeyboardMarkup:
    """
    Create model selection keyboard.
    
    Args:
        current_model: Currently selected model
    
    Layout:
    [GPT Image 1 (устаревшая) - disabled]
    [GPT Image 1.5 ✓]
    [◀️ Назад в меню]
    """
    builder = InlineKeyboardBuilder()
    
    # GPT Image 1 - disabled (показываем но не даём выбрать)
    builder.row(
        InlineKeyboardButton(
            text="🚫 GPT Image 1 (устаревшая)",
            callback_data="model:disabled",
        )
    )
    
    # GPT Image 1.5 - active
    gpt15_text = "✅ GPT Image 1.5 (Улучшенная)" if current_model == "gpt-image-1.5" else "GPT Image 1.5 (Улучшенная)"
    builder.row(
        InlineKeyboardButton(
            text=gpt15_text,
            callback_data="model:gpt-image-1.5",
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


def tokens_keyboard() -> InlineKeyboardMarkup:
    """
    Create tokens purchase keyboard with shop packages.
    
    Layout:
    [🐣 Starter] [✨ Small]
    [🔥 Medium]  [😎 Pro]
    [👑 Vip                ]
    [📞 Связаться с менеджером]
    [◀️ Назад в меню]
    """
    builder = InlineKeyboardBuilder()
    
    # Row 1: Starter + Small
    builder.row(
        InlineKeyboardButton(
            text="🐣 Starter",
            callback_data=CallbackData.SHOP_STARTER,
        ),
        InlineKeyboardButton(
            text="✨ Small",
            callback_data=CallbackData.SHOP_SMALL,
        ),
    )
    
    # Row 2: Medium + Pro
    builder.row(
        InlineKeyboardButton(
            text="🔥 Medium",
            callback_data=CallbackData.SHOP_MEDIUM,
        ),
        InlineKeyboardButton(
            text="😎 Pro",
            callback_data=CallbackData.SHOP_PRO,
        ),
    )
    
    # Row 3: VIP (full width)
    builder.row(
        InlineKeyboardButton(
            text="👑 Vip",
            callback_data=CallbackData.SHOP_VIP,
        ),
    )
    
    # Row 4: Contact manager
    builder.row(
        InlineKeyboardButton(
            text="📞 Связаться с менеджером",
            callback_data=CallbackData.SHOP_CONTACT,
        ),
    )
    
    # Row 5: Back to menu
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


def insufficient_balance_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for insufficient balance message.
    
    Layout:
    [💰 Перейти в магазин]
    [◀️ Назад в меню]
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💰 Перейти в магазин",
            callback_data=CallbackData.TOKENS,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()


def history_item_keyboard(task_id: int, has_image: bool) -> InlineKeyboardMarkup:
    """
    Create keyboard for history item.
    
    Args:
        task_id: The task ID
        has_image: Whether the task has a result image
    """
    builder = InlineKeyboardBuilder()
    
    if has_image:
        builder.row(
            InlineKeyboardButton(
                text="🖼 Показать изображение",
                callback_data=f"history:show:{task_id}",
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="history:back",
        )
    )
    
    return builder.as_markup()


def regenerate_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """
    Create keyboard with regenerate button for result message.
    
    Args:
        task_id: The task ID to regenerate
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Сгенерировать ещё",
            callback_data=f"{CallbackData.REGENERATE_PREFIX}{task_id}",
        )
    )
    
    return builder.as_markup()
