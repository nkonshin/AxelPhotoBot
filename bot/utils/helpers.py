"""
Helper utility functions for the Telegram bot.

Contains validation and formatting functions used across handlers.
"""

from datetime import datetime
from typing import Optional, List, Any

from bot.utils.messages import (
    format_task_status,
    format_task_type,
    PROFILE_HISTORY_ITEM,
)


# =============================================================================
# IMAGE FORMAT VALIDATION (Requirements 4.4)
# =============================================================================

# Supported MIME types for image uploads
SUPPORTED_MIME_TYPES = frozenset({
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
})

# Supported file extensions
SUPPORTED_EXTENSIONS = frozenset({
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
})


def validate_image_format(
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> bool:
    """
    Validate that the image format is supported.
    
    Checks both MIME type and file extension to determine if the image
    format is supported for editing operations.
    
    Args:
        file_name: Original file name (optional)
        mime_type: MIME type of the file (optional)
    
    Returns:
        True if format is supported, False otherwise
    
    Examples:
        >>> validate_image_format(mime_type="image/png")
        True
        >>> validate_image_format(file_name="photo.jpg")
        True
        >>> validate_image_format(file_name="document.pdf")
        False
        >>> validate_image_format(mime_type="application/pdf")
        False
    """
    # Check MIME type first (more reliable)
    if mime_type:
        if mime_type.lower() in SUPPORTED_MIME_TYPES:
            return True
    
    # Fall back to file extension check
    if file_name:
        file_name_lower = file_name.lower()
        for ext in SUPPORTED_EXTENSIONS:
            if file_name_lower.endswith(ext):
                return True
    
    return False


def get_supported_formats_text() -> str:
    """
    Get human-readable list of supported image formats.
    
    Returns:
        String listing supported formats
    """
    return "JPG, PNG, WEBP"


# =============================================================================
# DATE/TIME FORMATTING
# =============================================================================

def format_date(dt: Optional[datetime]) -> str:
    """
    Format datetime for display in Russian locale format.
    
    Args:
        dt: Datetime object to format
    
    Returns:
        Formatted date string (DD.MM.YYYY HH:MM) or "—" if None
    
    Examples:
        >>> from datetime import datetime
        >>> format_date(datetime(2025, 12, 25, 14, 30))
        '25.12.2025 14:30'
        >>> format_date(None)
        '—'
    """
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date_short(dt: Optional[datetime]) -> str:
    """
    Format datetime in short format (date only).
    
    Args:
        dt: Datetime object to format
    
    Returns:
        Formatted date string (DD.MM.YYYY) or "—" if None
    """
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y")


# =============================================================================
# HISTORY FORMATTING (Requirements 10.3)
# =============================================================================

def truncate_text(text: str, max_length: int = 30, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add when truncated
    
    Returns:
        Truncated text with suffix if needed
    
    Examples:
        >>> truncate_text("Short text", 30)
        'Short text'
        >>> truncate_text("This is a very long text that needs truncation", 20)
        'This is a very long ...'
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix


def format_history_item(
    index: int,
    task_type: str,
    status: str,
    created_at: Optional[datetime],
    prompt: str,
    max_prompt_length: int = 30,
) -> str:
    """
    Format a single history item for display.
    
    Args:
        index: Item number (1-based)
        task_type: Task type ("generate" or "edit")
        status: Task status
        created_at: Task creation datetime
        prompt: Task prompt
        max_prompt_length: Maximum prompt length before truncation
    
    Returns:
        Formatted history item string
    """
    return PROFILE_HISTORY_ITEM.format(
        index=index,
        task_type=format_task_type(task_type),
        status=format_task_status(status),
        date=format_date(created_at),
        prompt=truncate_text(prompt, max_prompt_length),
    )


def format_history_list(
    tasks: List[Any],
    max_items: int = 10,
    max_prompt_length: int = 30,
) -> str:
    """
    Format a list of tasks as history for display.
    
    Args:
        tasks: List of GenerationTask objects
        max_items: Maximum number of items to include
        max_prompt_length: Maximum prompt length before truncation
    
    Returns:
        Formatted history string
    
    Note:
        Tasks should have: task_type, status, created_at, prompt attributes
    """
    if not tasks:
        return ""
    
    lines = []
    for i, task in enumerate(tasks[:max_items], 1):
        lines.append(format_history_item(
            index=i,
            task_type=task.task_type,
            status=task.status,
            created_at=task.created_at,
            prompt=task.prompt,
            max_prompt_length=max_prompt_length,
        ))
    
    return "".join(lines)


# =============================================================================
# PROMPT FORMATTING
# =============================================================================

def format_prompt_preview(prompt: str, max_length: int = 500) -> str:
    """
    Format prompt for preview display.
    
    Args:
        prompt: Full prompt text
        max_length: Maximum length before truncation
    
    Returns:
        Formatted prompt with ellipsis if truncated
    """
    return truncate_text(prompt, max_length)


# =============================================================================
# BALANCE FORMATTING
# =============================================================================

def format_balance_change(
    current: int,
    cost: int,
) -> tuple[int, int, int]:
    """
    Calculate balance change for display.
    
    Args:
        current: Current token balance
        cost: Cost of operation
    
    Returns:
        Tuple of (cost, current_balance, balance_after)
    """
    return cost, current, current - cost
