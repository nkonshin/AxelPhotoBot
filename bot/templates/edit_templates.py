"""
Шаблоны промптов для редактирования фото.

Этот файл содержит готовые шаблоны для раздела "Идеи и тренды".
Вы можете легко изменять названия кнопок и промпты здесь.

Каждый шаблон содержит:
- id: уникальный идентификатор (не менять!)
- name: название кнопки (можно менять)
- description: описание для пользователя (можно менять)
- prompt: текст промпта для редактирования (можно менять)
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EditTemplate:
    """Шаблон для редактирования фото."""
    
    id: str
    name: str  # Название кнопки
    description: str  # Описание шаблона
    prompt: str  # Промпт для редактирования


# =============================================================================
# НАСТРОЙКА ШАБЛОНОВ
# Измените названия кнопок и промпты ниже по своему усмотрению
# =============================================================================

EDIT_TEMPLATES: List[EditTemplate] = [
    EditTemplate(
        id="trend_collage_female",
        name="👩 Трендовый женский коллаж",
        description="Создание стильного коллажа с вашим фото",
        prompt=(
            "Create a trendy aesthetic collage with the person from the photo. "
            "Include soft pastel colors, dreamy atmosphere, fashion magazine style, "
            "artistic composition with multiple frames, elegant typography elements, "
            "high fashion editorial look, professional retouching, soft lighting"
        ),
    ),
    EditTemplate(
        id="trend_collage_male",
        name="👨 Трендовый мужской коллаж",
        description="Создание стильного мужского коллажа",
        prompt=(
            "Create a trendy masculine collage with the person from the photo. "
            "Include bold colors, urban atmosphere, GQ magazine style, "
            "artistic composition with geometric frames, modern typography, "
            "high fashion editorial look, professional retouching, dramatic lighting"
        ),
    ),
    EditTemplate(
        id="cinematic_portrait",
        name="🎬 Кинематографичный портрет",
        description="Портрет в стиле голливудского кино",
        prompt=(
            "Transform into a cinematic movie portrait. Hollywood style lighting, "
            "dramatic shadows, film grain effect, anamorphic lens flare, "
            "professional color grading, movie poster quality, "
            "depth of field, atmospheric mood, 35mm film look"
        ),
    ),
    EditTemplate(
        id="neon_cyberpunk",
        name="🌃 Неоновый киберпанк",
        description="Футуристический стиль с неоновыми огнями",
        prompt=(
            "Transform into cyberpunk neon style. Vibrant neon lights in pink and blue, "
            "futuristic city background, rain reflections, holographic elements, "
            "Blade Runner atmosphere, high contrast, glowing effects, "
            "sci-fi aesthetic, night city vibes"
        ),
    ),
]


# =============================================================================
# ССЫЛКА НА КАНАЛ С ПРИМЕРАМИ
# Измените URL на свой канал
# =============================================================================

EXAMPLES_CHANNEL_URL = "https://t.me/nanobananabot_examples"
EXAMPLES_BUTTON_TEXT = "📚 Больше примеров"


# =============================================================================
# ФУНКЦИИ (не изменять)
# =============================================================================

def get_edit_template_by_id(template_id: str) -> Optional[EditTemplate]:
    """Получить шаблон по ID."""
    return next((t for t in EDIT_TEMPLATES if t.id == template_id), None)


def get_all_edit_templates() -> List[EditTemplate]:
    """Получить все шаблоны."""
    return EDIT_TEMPLATES.copy()
