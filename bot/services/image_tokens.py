"""Utilities for image token estimation and parameter validation.

The bot uses a user-friendly "token" system for billing.
This module handles the mapping between quality settings and token costs.

Token Economy:
- Low quality: 2 tokens
- Medium quality: 5 tokens  
- High quality: 20 tokens

Additional images cost:
- 1-3 images: free (included in base cost)
- 4-6 images: +1 token
- 7-10 images: +2 tokens total (+1 more)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ImageQuality = Literal["low", "medium", "high"]
ImageSize = Literal["1024x1024", "1024x1536", "1536x1024"]


@dataclass(frozen=True)
class ImageParams:
    """Image generation parameters used by the bot."""

    quality: ImageQuality
    size: ImageSize


# User-facing token costs (simple, user-friendly)
USER_TOKEN_COSTS: dict[ImageQuality, int] = {
    "low": 2,
    "medium": 5,
    "high": 20,
}


# API token costs for internal tracking (actual OpenAI token usage)
# These are stored separately for admin analytics
API_TOKEN_TABLE: dict[ImageQuality, dict[ImageSize, int]] = {
    "low": {
        "1024x1024": 272,
        "1024x1536": 408,
        "1536x1024": 400,
    },
    "medium": {
        "1024x1024": 1056,
        "1024x1536": 1584,
        "1536x1024": 1568,
    },
    "high": {
        "1024x1024": 4160,
        "1024x1536": 6240,
        "1536x1024": 6208,
    },
}


IMAGE_SIZE_LABELS: dict[ImageSize, str] = {
    "1024x1024": "Квадрат (1024×1024)",
    "1024x1536": "Портрет (1024×1536)",
    "1536x1024": "Альбом (1536×1024)",
}


IMAGE_QUALITY_LABELS: dict[ImageQuality, str] = {
    "low": "Быстрое",
    "medium": "Стандарт",
    "high": "Максимум",
}


def estimate_image_tokens(quality: ImageQuality, size: ImageSize = "1024x1024") -> int:
    """Return the user-facing token cost for the given quality.
    
    Size does not affect user token cost (only quality matters).
    """
    return USER_TOKEN_COSTS[quality]


def estimate_api_tokens(quality: ImageQuality, size: ImageSize) -> int:
    """Return the actual API token cost for internal tracking."""
    return API_TOKEN_TABLE[quality][size]


def calculate_extra_images_cost(images_count: int) -> int:
    """Calculate extra token cost for multiple input images.
    
    Rules:
    - 1-3 images: free (included in base cost)
    - 4-6 images: +1 token
    - 7-10 images: +2 tokens total
    
    Args:
        images_count: Number of input images (1-10)
    
    Returns:
        Extra tokens to add to base cost
    """
    if images_count <= 3:
        return 0
    elif images_count <= 6:
        return 1
    else:  # 7-10
        return 2


def calculate_total_cost(quality: ImageQuality, images_count: int = 1) -> int:
    """Calculate total token cost including extra images.
    
    Args:
        quality: Image quality setting
        images_count: Number of input images (for edit operations)
    
    Returns:
        Total token cost
    """
    base_cost = USER_TOKEN_COSTS[quality]
    extra_cost = calculate_extra_images_cost(images_count)
    return base_cost + extra_cost


def is_valid_quality(value: str) -> bool:
    """Validate image quality string."""
    return value in ("low", "medium", "high")


def is_valid_size(value: str) -> bool:
    """Validate image size string."""
    return value in ("1024x1024", "1024x1536", "1536x1024")
