"""FSM states for admin flows."""

from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    """States for the broadcast flow."""
    
    # Admin is entering the broadcast message
    waiting_message = State()
    
    # Admin is confirming the broadcast
    confirm_broadcast = State()
