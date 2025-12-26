"""Utilities for image token estimation and parameter validation.

The bot uses an internal "token" balance that is intended to approximate OpenAI image
usage. This module centralizes the mapping between (quality, size) and the expected
image token cost.
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


IMAGE_TOKEN_TABLE: dict[ImageQuality, dict[ImageSize, int]] = {
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
    "1024x1024": "Square (1024×1024)",
    "1024x1536": "Portrait (1024×1536)",
    "1536x1024": "Landscape (1536×1024)",
}


IMAGE_QUALITY_LABELS: dict[ImageQuality, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}


def estimate_image_tokens(quality: ImageQuality, size: ImageSize) -> int:
    """Return the expected image token cost for the given parameters."""

    return IMAGE_TOKEN_TABLE[quality][size]


def is_valid_quality(value: str) -> bool:
    """Validate image quality string."""

    return value in ("low", "medium", "high")


def is_valid_size(value: str) -> bool:
    """Validate image size string."""

    return value in ("1024x1024", "1024x1536", "1536x1024")
