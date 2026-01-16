"""Utilities for image token estimation and parameter validation.

The bot uses a user-friendly "token" system for billing.
This module handles the mapping between quality settings and token costs.

Token Economy (GPT Image 1.5):
- Low quality: 2 tokens
- Medium quality: 5 tokens  
- High quality: 20 tokens

Token Economy (SeeDream 4.5):
- 2K quality: 5 tokens
- 4K quality: 7 tokens

Additional images cost:
- 1-3 images: free (included in base cost)
- 4-6 images: +1 token
- 7-10 images: +2 tokens total (+1 more)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ImageQuality = Literal["low", "medium", "high", "2k", "4k"]
ImageSize = Literal["1024x1024", "1024x1536", "1536x1024"]


@dataclass(frozen=True)
class ImageParams:
    """Image generation parameters used by the bot."""

    quality: ImageQuality
    size: ImageSize


# User-facing token costs for GPT Image models
GPT_TOKEN_COSTS: dict[str, int] = {
    "low": 2,
    "medium": 5,
    "high": 20,
}

# User-facing token costs for SeeDream model
SEEDREAM_TOKEN_COSTS: dict[str, int] = {
    "2k": 5,
    "4k": 5,
}

# Combined costs (for backward compatibility)
USER_TOKEN_COSTS: dict[str, int] = {
    **GPT_TOKEN_COSTS,
    **SEEDREAM_TOKEN_COSTS,
}


# API token costs for internal tracking (actual OpenAI token usage)
# These are stored separately for admin analytics
API_TOKEN_TABLE: dict[str, dict[ImageSize, int]] = {
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
    # SeeDream uses flat pricing per image
    "2k": {
        "1024x1024": 1000,
        "1024x1536": 1000,
        "1536x1024": 1000,
    },
    "4k": {
        "1024x1024": 1500,
        "1024x1536": 1500,
        "1536x1024": 1500,
    },
}


IMAGE_SIZE_LABELS: dict[ImageSize, str] = {
    "1024x1024": "Квадрат",
    "1024x1536": "Портрет",
    "1536x1024": "Альбом",
}


# Quality labels for GPT Image models
IMAGE_QUALITY_LABELS: dict[str, str] = {
    "low": "Быстрое",
    "medium": "Стандарт",
    "high": "Максимум",
}

# Quality labels for SeeDream model
SEEDREAM_QUALITY_LABELS: dict[str, str] = {
    "2k": "2K",
    "4k": "4K",
}


def is_seedream_model(model: str | None) -> bool:
    """Check if the model is SeeDream."""
    return model is not None and model.startswith("seedream")


def get_quality_labels_for_model(model: str | None) -> dict[str, str]:
    """Get quality labels based on model."""
    if is_seedream_model(model):
        return SEEDREAM_QUALITY_LABELS
    return IMAGE_QUALITY_LABELS


def get_default_quality_for_model(model: str | None) -> str:
    """Get default quality for model."""
    if is_seedream_model(model):
        return "2k"
    return "medium"


def estimate_image_tokens(quality: str, size: ImageSize = "1024x1024", model: str | None = None) -> int:
    """Return the user-facing token cost for the given quality.
    
    Size does not affect user token cost (only quality matters).
    """
    # Use appropriate cost table based on model
    if is_seedream_model(model):
        return SEEDREAM_TOKEN_COSTS.get(quality, 5)  # Default to 2k cost
    return GPT_TOKEN_COSTS.get(quality, 5)  # Default to medium cost


def estimate_api_tokens(quality: str, size: ImageSize) -> int:
    """Return the actual API token cost for internal tracking."""
    if quality in API_TOKEN_TABLE and size in API_TOKEN_TABLE[quality]:
        return API_TOKEN_TABLE[quality][size]
    return 1000  # Default fallback


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


def calculate_total_cost(quality: str, images_count: int = 1, model: str | None = None) -> int:
    """Calculate total token cost including extra images.
    
    Args:
        quality: Image quality setting
        images_count: Number of input images (for edit operations)
        model: Model name (to determine pricing)
    
    Returns:
        Total token cost
    """
    base_cost = estimate_image_tokens(quality, model=model)
    extra_cost = calculate_extra_images_cost(images_count)
    return base_cost + extra_cost


def is_valid_quality(value: str, model: str | None = None) -> bool:
    """Validate image quality string based on model."""
    if is_seedream_model(model):
        return value in ("2k", "4k")
    return value in ("low", "medium", "high")


def is_valid_size(value: str) -> bool:
    """Validate image size string."""
    return value in ("1024x1024", "1024x1536", "1536x1024")


def convert_quality_for_model(quality: str, target_model: str | None) -> str:
    """Convert quality setting when switching models.
    
    Maps GPT qualities to SeeDream and vice versa.
    """
    if is_seedream_model(target_model):
        # GPT -> SeeDream
        mapping = {
            "low": "2k",
            "medium": "2k",
            "high": "4k",
        }
        return mapping.get(quality, "2k")
    else:
        # SeeDream -> GPT
        mapping = {
            "2k": "medium",
            "4k": "high",
        }
        return mapping.get(quality, "medium")


def get_actual_resolution(model: str | None, quality: str, size: str) -> str:
    """
    Get the actual resolution for the given model, quality, and size.
    
    For SeeDream:
    - 2K quality: 2048x2048 (square), 2048x3072 (portrait), 3072x2048 (landscape)
    - 4K quality: 4096x4096 (all aspect ratios)
    
    For GPT Image models:
    - Returns the size as-is (1024x1024, 1024x1536, 1536x1024)
    
    Args:
        model: Model name
        quality: Quality setting (2k, 4k for SeeDream; low, medium, high for GPT)
        size: Size setting (1024x1024, 1024x1536, 1536x1024)
    
    Returns:
        Actual resolution string (e.g., "2048x3072")
    """
    if is_seedream_model(model):
        # SeeDream resolution mapping
        if quality == "4k":
            return "4096x4096"
        else:  # 2k or default
            if size == "1024x1536":  # Portrait
                return "2048x3072"
            elif size == "1536x1024":  # Landscape
                return "3072x2048"
            else:  # Square
                return "2048x2048"
    else:
        # GPT Image models use the size as-is
        return size
