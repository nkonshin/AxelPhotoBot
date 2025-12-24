"""Predefined prompt templates for image generation."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PromptTemplate:
    """A predefined prompt template for image generation."""
    
    id: str
    name: str
    description: str
    prompt: str
    tokens_cost: int = 1


# Hardcoded templates for "Ideas and Trends" section
TEMPLATES: List[PromptTemplate] = [
    PromptTemplate(
        id="cyberpunk_portrait",
        name="🌆 Киберпанк портрет",
        description="Футуристический портрет в стиле Cyberpunk 2077",
        prompt=(
            "A stunning cyberpunk portrait, neon lights, futuristic city background, "
            "high detail, cinematic lighting, 8k quality, digital art style"
        ),
        tokens_cost=1,
    ),
    PromptTemplate(
        id="anime_character",
        name="🎌 Аниме персонаж",
        description="Персонаж в стиле японской анимации",
        prompt=(
            "Anime style character, vibrant colors, detailed eyes, "
            "studio ghibli inspired, beautiful background, high quality illustration"
        ),
        tokens_cost=1,
    ),
    PromptTemplate(
        id="oil_painting",
        name="🎨 Масляная живопись",
        description="Классическая картина маслом",
        prompt=(
            "Classical oil painting style, rich colors, visible brush strokes, "
            "museum quality, renaissance inspired, dramatic lighting"
        ),
        tokens_cost=1,
    ),
]


def get_template_by_id(template_id: str) -> Optional[PromptTemplate]:
    """
    Get a template by its ID.
    
    Args:
        template_id: The unique identifier of the template
    
    Returns:
        PromptTemplate if found, None otherwise
    """
    return next((t for t in TEMPLATES if t.id == template_id), None)


def get_all_templates() -> List[PromptTemplate]:
    """
    Get all available templates.
    
    Returns:
        List of all PromptTemplate objects
    """
    return TEMPLATES.copy()
