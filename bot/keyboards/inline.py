"""Inline keyboards for the bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.templates.prompts import get_all_templates
from bot.templates.edit_templates import (
    get_all_edit_templates,
    EXAMPLES_CHANNEL_URL,
    EXAMPLES_BUTTON_TEXT,
)
from bot.services.image_tokens import (
    IMAGE_QUALITY_LABELS,
    IMAGE_SIZE_LABELS,
    SEEDREAM_QUALITY_LABELS,
    ImageQuality,
    ImageSize,
    is_seedream_model,
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
    
    # Template prefix (old generation templates)
    TEMPLATE_PREFIX = "template:"
    
    # Edit template prefix (new edit templates for trends)
    EDIT_TEMPLATE_PREFIX = "edit_tpl:"
    
    # Template photos ready
    TEMPLATE_PHOTOS_READY = "tpl:photos_ready"
    TEMPLATE_ADD_MORE = "tpl:add_more"

    # Image settings
    IMAGE_QUALITY_PREFIX = "img:quality:"
    IMAGE_SIZE_PREFIX = "img:size:"
    
    # Regenerate
    REGENERATE_PREFIX = "regen:"
    
    # Feedback
    FEEDBACK_POSITIVE_PREFIX = "feedback:positive:"
    FEEDBACK_NEGATIVE_PREFIX = "feedback:negative:"
    FEEDBACK_RETRY_PREFIX = "feedback:retry:"
    
    # Shop packages
    SHOP_STARTER = "shop:starter"
    SHOP_SMALL = "shop:small"
    SHOP_MEDIUM = "shop:medium"
    SHOP_PRO = "shop:pro"
    SHOP_VIP = "shop:vip"
    SHOP_CONTACT = "shop:contact"
    
    # Gift
    GIFT = "menu:gift"


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
    Create the main menu keyboard with 7 buttons.
    
    Layout (full width buttons except middle row):
    [🎨 Создать картинку с нуля        ]
    [🪄 Редактировать твоё фото      ]
    [🤖 Выбрать модель          ]
    [👤 Личный кабинет] [💰 Купить токены]
    [🎁 Подарить фотосессию     ]
    [💡 Идеи и тренды           ]
    """
    builder = InlineKeyboardBuilder()
    
    # Full width buttons
    builder.row(
        InlineKeyboardButton(
            text="🎨 Создать картинку с нуля",
            callback_data=CallbackData.GENERATE,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🪄 Редактировать твоё фото",
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
    # Gift button (full width)
    builder.row(
        InlineKeyboardButton(
            text="🎁 Подарить фотосессию",
            callback_data=CallbackData.GIFT,
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
    current_quality: str,
    current_size: ImageSize,
    confirm_callback_data: str = CallbackData.CONFIRM,
    model: str | None = None,
) -> InlineKeyboardMarkup:
    """Create keyboard to select image quality/size and confirm/cancel.
    
    For GPT models: 3 quality buttons (low/medium/high)
    For SeeDream: 2 quality buttons (2K/4K)
    """

    builder = InlineKeyboardBuilder()

    # Quality row - different buttons based on model
    if is_seedream_model(model):
        # SeeDream: 2K and 4K buttons
        for quality in ("2k", "4k"):
            label = SEEDREAM_QUALITY_LABELS[quality]
            text = f"✅ {label}" if quality == current_quality else label
            builder.add(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"{CallbackData.IMAGE_QUALITY_PREFIX}{quality}",
                )
            )
        builder.adjust(2)
    else:
        # GPT: low/medium/high buttons
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

    # Size row (same for all models)
    for size in ("1024x1024", "1024x1536", "1536x1024"):
        label = IMAGE_SIZE_LABELS[size]
        text = f"✅ {label}" if size == current_size else label
        builder.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{CallbackData.IMAGE_SIZE_PREFIX}{size}",
            )
        )
    
    # Adjust: quality buttons + 3 size buttons
    if is_seedream_model(model):
        builder.adjust(2, 3)
    else:
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
    Create keyboard with edit template options for "Идеи и тренды".
    
    Shows 4 edit templates + link to examples channel.
    """
    builder = InlineKeyboardBuilder()
    
    # Add edit templates (4 buttons)
    templates = get_all_edit_templates()
    for template in templates:
        builder.row(
            InlineKeyboardButton(
                text=template.name,
                callback_data=f"{CallbackData.EDIT_TEMPLATE_PREFIX}{template.id}",
            )
        )
    
    # Add "More examples" button with link to channel
    builder.row(
        InlineKeyboardButton(
            text=EXAMPLES_BUTTON_TEXT,
            url=EXAMPLES_CHANNEL_URL,
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


def template_photos_keyboard(photos_count: int) -> InlineKeyboardMarkup:
    """
    Create keyboard for template photo upload flow.
    
    Shows "Ready" button and photo count.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Готово ({photos_count} фото)",
            callback_data=CallbackData.TEMPLATE_PHOTOS_READY,
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Отмена",
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
    [SeeDream 4.5 ✓]
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

    # SeeDream 4.5 - active
    seedream_text = "✅ SeeDream 4.5 (Новейшая)" if current_model == "seedream-4-5" else "SeeDream 4.5 (Новейшая)"
    builder.row(
        InlineKeyboardButton(
            text=seedream_text,
            callback_data="model:seedream-4-5",
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


def subscription_keyboard(channel: str) -> InlineKeyboardMarkup:
    """
    Create keyboard for subscription check.
    
    Args:
        channel: Channel username (e.g., @nkonshin_ai)
    """
    builder = InlineKeyboardBuilder()
    
    # Remove @ for URL
    channel_name = channel.replace("@", "")
    
    builder.row(
        InlineKeyboardButton(
            text="📢 Подписаться на канал",
            url=f"https://t.me/{channel_name}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Я подписался",
            callback_data="check_subscription",
        )
    )
    
    return builder.as_markup()


def result_feedback_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """
    Create keyboard with feedback buttons and quick actions for generation result.
    
    Args:
        task_id: The task ID for feedback
    
    Layout:
    [🔄 Сгенерировать ещё раз                    ]
    [✏️ Изменить промпт            ]
    [👍] [👎]
    [🏠 Главное меню]
    """
    builder = InlineKeyboardBuilder()
    
    # Regenerate button (full width)
    builder.row(
        InlineKeyboardButton(
            text="🔄 Сгенерировать ещё раз",
            callback_data=f"{CallbackData.REGENERATE_PREFIX}{task_id}",
        ),
    )
    
    # Edit prompt button (full width)
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить промпт",
            callback_data=f"edit_prompt:{task_id}",
        ),
    )
    
    # Feedback row
    builder.row(
        InlineKeyboardButton(
            text="👍",
            callback_data=f"{CallbackData.FEEDBACK_POSITIVE_PREFIX}{task_id}",
        ),
        InlineKeyboardButton(
            text="👎",
            callback_data=f"{CallbackData.FEEDBACK_NEGATIVE_PREFIX}{task_id}",
        ),
    )
    
    # Main menu button (full width)
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu",
        ),
    )
    
    return builder.as_markup()


def negative_feedback_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """
    Create keyboard shown after negative feedback.
    
    Args:
        task_id: The task ID for retry
    
    Layout:
    [🔄 Попробовать снова]
    [◀️ В меню]
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Попробовать снова",
            callback_data=f"{CallbackData.FEEDBACK_RETRY_PREFIX}{task_id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ В меню",
            callback_data=CallbackData.BACK_TO_MENU,
        )
    )
    
    return builder.as_markup()
