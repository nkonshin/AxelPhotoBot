"""FSM states for image generation and editing flows."""

from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    """States for the image generation flow (Создать картинку с нуля)."""
    
    # User is entering the text prompt for generation
    waiting_prompt = State()
    
    # User is confirming the generation (sees cost and balance)
    confirm_generation = State()


class EditStates(StatesGroup):
    """States for the image editing flow (Редактировать твоё фото)."""
    
    # User is uploading images to edit (supports multiple)
    waiting_image = State()
    
    # User is entering the edit description/prompt
    waiting_edit_prompt = State()
    
    # User is confirming the edit (sees cost and balance)
    confirm_edit = State()


class TemplateStates(StatesGroup):
    """States for the template selection flow (Идеи и тренды)."""
    
    # User is confirming generation from a template
    confirm_template = State()
