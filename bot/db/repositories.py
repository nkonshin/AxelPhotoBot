"""Repository classes for database CRUD operations."""

from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import config
from bot.db.models import User, GenerationTask


class UserRepository:
    """Repository for User CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> tuple[User, bool]:
        """
        Get existing user or create a new one.
        
        Returns:
            Tuple of (user, created) where created is True if new user was created.
        """
        user = await self.get_by_telegram_id(telegram_id)
        
        if user is not None:
            return user, False
        
        # Create new user with initial tokens
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            tokens=config.initial_tokens,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user, True
    
    async def update_tokens(self, user_id: int, tokens_delta: int) -> Optional[User]:
        """
        Update user's token balance.
        
        Args:
            user_id: User's database ID
            tokens_delta: Amount to add (positive) or subtract (negative)
        
        Returns:
            Updated user or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            return None
        
        user.tokens += tokens_delta
        await self.session.commit()
        await self.session.refresh(user)
        
        return user


class TaskRepository:
    """Repository for GenerationTask CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        task_type: str,
        prompt: str,
        tokens_spent: int,
        source_image_url: Optional[str] = None,
    ) -> GenerationTask:
        """
        Create a new generation task.
        
        Args:
            user_id: User's database ID
            task_type: "generate" or "edit"
            prompt: Text prompt for generation
            tokens_spent: Number of tokens spent
            source_image_url: Source image URL for edit tasks
        
        Returns:
            Created GenerationTask
        """
        task = GenerationTask(
            user_id=user_id,
            task_type=task_type,
            prompt=prompt,
            tokens_spent=tokens_spent,
            source_image_url=source_image_url,
            status="pending",
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        
        return task
    
    async def update_status(
        self,
        task_id: int,
        status: str,
        result_image_url: Optional[str] = None,
        error_message: Optional[str] = None,
        increment_retry: bool = False,
    ) -> Optional[GenerationTask]:
        """
        Update task status and related fields.
        
        Args:
            task_id: Task's database ID
            status: New status ("pending", "processing", "done", "failed")
            result_image_url: URL of generated image (for "done" status)
            error_message: Error message (for "failed" status)
            increment_retry: Whether to increment retry count
        
        Returns:
            Updated task or None if not found
        """
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task is None:
            return None
        
        task.status = status
        
        if result_image_url is not None:
            task.result_image_url = result_image_url
        
        if error_message is not None:
            task.error_message = error_message
        
        if increment_retry:
            task.retry_count += 1
        
        await self.session.commit()
        await self.session.refresh(task)
        
        return task
    
    async def get_user_history(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[GenerationTask]:
        """
        Get user's generation history.
        
        Args:
            user_id: User's database ID
            limit: Maximum number of tasks to return (default 10)
        
        Returns:
            List of GenerationTask ordered by created_at descending
        """
        result = await self.session.execute(
            select(GenerationTask)
            .where(GenerationTask.user_id == user_id)
            .order_by(desc(GenerationTask.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_by_id(self, task_id: int) -> Optional[GenerationTask]:
        """Get task by ID."""
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        return result.scalar_one_or_none()
