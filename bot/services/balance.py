"""Balance service for token operations."""

import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, GenerationTask

logger = logging.getLogger(__name__)


class InsufficientBalanceError(Exception):
    """Raised when user doesn't have enough tokens."""
    
    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient balance: required {required}, available {available}"
        )


class BalanceService:
    """Service for managing user token balance."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def check_balance(self, user_id: int, required_tokens: int) -> bool:
        """
        Check if user has enough tokens.
        
        Args:
            user_id: User's database ID
            required_tokens: Number of tokens required
        
        Returns:
            True if user has enough tokens, False otherwise
        """
        result = await self.session.execute(
            select(User.tokens).where(User.id == user_id)
        )
        tokens = result.scalar_one_or_none()
        
        if tokens is None:
            return False
        
        return tokens >= required_tokens
    
    async def deduct_tokens(
        self,
        user_id: int,
        amount: int,
        raise_on_insufficient: bool = True,
    ) -> Optional[User]:
        """
        Deduct tokens from user's balance.
        
        Args:
            user_id: User's database ID
            amount: Number of tokens to deduct
            raise_on_insufficient: If True, raise InsufficientBalanceError
        
        Returns:
            Updated user or None if not found
        
        Raises:
            InsufficientBalanceError: If user doesn't have enough tokens
        """
        # Atomic update: deduct only if balance is sufficient
        stmt = (
            update(User)
            .where(User.id == user_id)
            .where(User.tokens >= amount)
            .values(tokens=User.tokens - amount)
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            # Either user not found or insufficient balance
            user_result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            existing = user_result.scalar_one_or_none()
            if existing is None:
                return None
            if raise_on_insufficient:
                raise InsufficientBalanceError(required=amount, available=existing.tokens)
            return None

        await self.session.commit()
        # Refresh to get updated state
        user_result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return user_result.scalar_one_or_none()
    
    async def refund_tokens(self, user_id: int, amount: int) -> Optional[User]:
        """
        Refund tokens to user's balance.
        
        Args:
            user_id: User's database ID
            amount: Number of tokens to refund
        
        Returns:
            Updated user or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            return None
        
        user.tokens += amount
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def refund_task(self, task_id: int) -> Optional[User]:
        """
        Refund tokens for a failed task.
        
        Args:
            task_id: Task's database ID
        
        Returns:
            Updated user or None if task not found
        """
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task is None:
            return None
        
        return await self.refund_tokens(task.user_id, task.tokens_spent)
