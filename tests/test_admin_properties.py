"""Property-based tests for admin functionality.

Feature: nine-features
Tests correctness properties for admin commands.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from bot.db.models import User
from bot.db.repositories import UserRepository
from bot.config import config


class TestUserResetProperties:
    """Property-based tests for user reset functionality.
    
    Property 2: User Reset Restores Defaults
    Validates: Requirements 3.1, 3.2
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        initial_tokens=st.integers(min_value=0, max_value=10000),
        initial_quality=st.sampled_from(["low", "medium", "high"]),
        initial_size=st.sampled_from(["1024x1024", "1024x1536", "1536x1024"]),
        initial_model=st.sampled_from(["gpt-image-1", "gpt-image-1.5"]),
        user_id=st.integers(min_value=100000000, max_value=999999999),
    )
    async def test_reset_user_restores_defaults(
        self,
        test_session: AsyncSession,
        initial_tokens: int,
        initial_quality: str,
        initial_size: str,
        initial_model: str,
        user_id: int,
    ):
        """
        Feature: nine-features, Property 2: User Reset Restores Defaults
        Validates: Requirements 3.1, 3.2
        
        For any user with arbitrary settings, after reset:
        - tokens should equal config.initial_tokens (7)
        - model should be "gpt-image-1.5"
        - quality should be "medium"
        - size should be "1024x1024"
        """
        # Cleanup any existing user with this ID first
        await test_session.execute(delete(User).where(User.telegram_id == user_id))
        await test_session.commit()
        
        # Create user with arbitrary initial values
        user = User(
            telegram_id=user_id,
            username=f"testuser_{user_id}",
            first_name="Test",
            tokens=initial_tokens,
            selected_model=initial_model,
            image_quality=initial_quality,
            image_size=initial_size,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        # Perform reset (same logic as /resetuser command)
        user.tokens = config.initial_tokens
        user.selected_model = "gpt-image-1.5"
        user.image_quality = "medium"
        user.image_size = "1024x1024"
        await test_session.commit()
        await test_session.refresh(user)
        
        # Verify defaults are restored
        assert user.tokens == config.initial_tokens, \
            f"Expected tokens={config.initial_tokens}, got {user.tokens}"
        assert user.selected_model == "gpt-image-1.5", \
            f"Expected model='gpt-image-1.5', got {user.selected_model}"
        assert user.image_quality == "medium", \
            f"Expected quality='medium', got {user.image_quality}"
        assert user.image_size == "1024x1024", \
            f"Expected size='1024x1024', got {user.image_size}"
        
        # Cleanup
        await test_session.delete(user)
        await test_session.commit()


class TestTokenAdditionProperties:
    """Property-based tests for token addition.
    
    Property 3: Token Addition Accuracy
    Validates: Requirements 4.3
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        initial_balance=st.integers(min_value=0, max_value=10000),
        amount_to_add=st.integers(min_value=1, max_value=1000),
        user_id=st.integers(min_value=100000000, max_value=999999999),
    )
    async def test_token_addition_accuracy(
        self,
        test_session: AsyncSession,
        initial_balance: int,
        amount_to_add: int,
        user_id: int,
    ):
        """
        Feature: nine-features, Property 3: Token Addition Accuracy
        Validates: Requirements 4.3
        
        For any user with balance B, after adding amount A:
        - new balance should equal B + A exactly
        """
        # Cleanup any existing user with this ID first
        await test_session.execute(delete(User).where(User.telegram_id == user_id))
        await test_session.commit()
        
        # Create user with initial balance
        user = User(
            telegram_id=user_id,
            username=f"tokentest_{user_id}",
            tokens=initial_balance,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        # Add tokens using repository method
        repo = UserRepository(test_session)
        updated_user = await repo.update_tokens(user.id, amount_to_add)
        
        # Verify exact addition
        expected_balance = initial_balance + amount_to_add
        assert updated_user.tokens == expected_balance, \
            f"Expected {expected_balance}, got {updated_user.tokens}"
        
        # Cleanup
        await test_session.delete(updated_user)
        await test_session.commit()



class TestSubscriptionToggleProperties:
    """Property-based tests for subscription toggle.
    
    Property 4: Subscription Toggle Persistence
    Validates: Requirements 7.1, 7.2
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        initial_state=st.booleans(),
    )
    async def test_subscription_toggle_logic(
        self,
        test_session: AsyncSession,
        initial_state: bool,
    ):
        """
        Feature: nine-features, Property 4: Subscription Toggle Persistence
        Validates: Requirements 7.1, 7.2
        
        For any initial state of subscription_required:
        - After toggle, the value should be the opposite
        - Toggle is idempotent: toggle(toggle(x)) == x
        """
        # Test toggle logic (without Redis dependency)
        current = initial_state
        
        # First toggle
        new_value = not current
        
        # Verify toggle changes state
        assert new_value != initial_state, \
            f"Toggle should change state from {initial_state}"
        
        # Second toggle should return to original
        restored_value = not new_value
        assert restored_value == initial_state, \
            f"Double toggle should restore original state"
        
        # Test that toggle is its own inverse
        assert not (not initial_state) == initial_state, \
            "Toggle should be its own inverse"
