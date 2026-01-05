"""Repository classes for database CRUD operations."""

from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, desc, func
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
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by database ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by Telegram username (without @)."""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_all_users(self) -> List[User]:
        """Get all users for broadcast."""
        result = await self.session.execute(
            select(User).order_by(User.id)
        )
        return list(result.scalars().all())
    
    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        referrer_id: Optional[int] = None,
    ) -> tuple[User, bool]:
        """
        Get existing user or create a new one.
        
        Args:
            telegram_id: User's Telegram ID
            username: User's Telegram username
            first_name: User's first name
            referrer_id: Database ID of the referrer (if any)
        
        Returns:
            Tuple of (user, created) where created is True if new user was created.
        """
        user = await self.get_by_telegram_id(telegram_id)
        
        if user is not None:
            return user, False

        # Create new user with initial tokens (7 free tokens)
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            tokens=config.initial_tokens,
            api_tokens_spent=0,
            referrer_id=referrer_id,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user, True
    
    async def get_referral_stats(self, user_id: int) -> dict:
        """
        Get referral statistics for a user.
        
        Args:
            user_id: User's database ID
        
        Returns:
            Dict with referral counts
        """
        # Count total referrals
        result = await self.session.execute(
            select(func.count(User.id))
            .where(User.referrer_id == user_id)
        )
        total_referrals = result.scalar() or 0
        
        return {
            "total_referrals": total_referrals,
        }
    
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
    
    async def update_model(self, user_id: int, model: str) -> Optional[User]:
        """
        Update user's selected model.
        
        Args:
            user_id: User's database ID
            model: Model name to set
        
        Returns:
            Updated user or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            return None
        
        user.selected_model = model
        await self.session.commit()
        await self.session.refresh(user)
        
        return user

    async def update_image_settings(
        self,
        user_id: int,
        image_quality: Optional[str] = None,
        image_size: Optional[str] = None,
    ) -> Optional[User]:
        """Update user's image generation settings."""

        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            return None

        if image_quality is not None:
            user.image_quality = image_quality

        if image_size is not None:
            user.image_size = image_size

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
        model: str = "gpt-image-1",
        image_quality: str = "medium",
        image_size: str = "1024x1024",
        source_image_url: Optional[str] = None,
        images_count: int = 1,
    ) -> GenerationTask:
        """
        Create a new generation task.
        
        Args:
            user_id: User's database ID
            task_type: "generate" or "edit"
            prompt: Text prompt for generation
            tokens_spent: Number of tokens spent (user tokens)
            model: Model name
            image_quality: Quality setting
            image_size: Size setting
            source_image_url: Source image URL for edit tasks
            images_count: Number of input images (for edit tasks)
        
        Returns:
            Created GenerationTask
        """
        task = GenerationTask(
            user_id=user_id,
            task_type=task_type,
            model=model,
            image_quality=image_quality,
            image_size=image_size,
            prompt=prompt,
            tokens_spent=tokens_spent,
            source_image_url=source_image_url,
            images_count=images_count,
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
        result_file_id: Optional[str] = None,
        error_message: Optional[str] = None,
        increment_retry: bool = False,
        api_tokens_spent: Optional[int] = None,
    ) -> Optional[GenerationTask]:
        """
        Update task status and related fields.
        
        Args:
            task_id: Task's database ID
            status: New status ("pending", "processing", "done", "failed")
            result_image_url: URL of generated image (for "done" status)
            result_file_id: Telegram file_id of result
            error_message: Error message (for "failed" status)
            increment_retry: Whether to increment retry count
            api_tokens_spent: API tokens used (for admin tracking)
        
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

        if result_file_id is not None:
            task.result_file_id = result_file_id
        
        if error_message is not None:
            task.error_message = error_message
        
        if increment_retry:
            task.retry_count += 1
        
        if api_tokens_spent is not None:
            task.api_tokens_spent = api_tokens_spent
        
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

    async def count_user_tasks_since(
        self,
        user_id: int,
        hours: int = 1,
    ) -> int:
        """
        Count user's tasks created in the last N hours.
        Used for rate limiting.
        
        Args:
            user_id: User's database ID
            hours: Number of hours to look back
        
        Returns:
            Number of tasks created in the time period
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(func.count(GenerationTask.id))
            .where(GenerationTask.user_id == user_id)
            .where(GenerationTask.created_at >= since)
        )
        return result.scalar() or 0


class StatsRepository:
    """Repository for statistics queries."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_total_users(self) -> int:
        """Get total number of users."""
        result = await self.session.execute(
            select(func.count(User.id))
        )
        return result.scalar() or 0
    
    async def get_total_tasks(self) -> int:
        """Get total number of tasks."""
        result = await self.session.execute(
            select(func.count(GenerationTask.id))
        )
        return result.scalar() or 0
    
    async def get_tasks_by_status(self) -> dict:
        """Get task counts grouped by status."""
        result = await self.session.execute(
            select(
                GenerationTask.status,
                func.count(GenerationTask.id)
            ).group_by(GenerationTask.status)
        )
        return {row[0]: row[1] for row in result.all()}
    
    async def get_total_tokens_spent(self) -> int:
        """Get total tokens spent across all tasks."""
        result = await self.session.execute(
            select(func.sum(GenerationTask.tokens_spent))
        )
        return result.scalar() or 0
    
    async def get_tasks_today(self) -> int:
        """Get number of tasks created today."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count(GenerationTask.id))
            .where(GenerationTask.created_at >= today)
        )
        return result.scalar() or 0
    
    async def get_users_today(self) -> int:
        """Get number of users registered today."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count(User.id))
            .where(User.created_at >= today)
        )
        return result.scalar() or 0
    
    async def get_active_users_today(self) -> int:
        """Get number of users who created tasks today."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count(func.distinct(GenerationTask.user_id)))
            .where(GenerationTask.created_at >= today)
        )
        return result.scalar() or 0
    
    async def get_top_users(self, limit: int = 10) -> List[tuple]:
        """Get top users by number of tasks."""
        result = await self.session.execute(
            select(
                User.telegram_id,
                User.username,
                User.first_name,
                func.count(GenerationTask.id).label("task_count")
            )
            .join(GenerationTask, User.id == GenerationTask.user_id)
            .group_by(User.id)
            .order_by(desc("task_count"))
            .limit(limit)
        )
        return result.all()
    
    async def get_model_usage(self) -> dict:
        """Get task counts grouped by model."""
        result = await self.session.execute(
            select(
                GenerationTask.model,
                func.count(GenerationTask.id)
            ).group_by(GenerationTask.model)
        )
        return {row[0]: row[1] for row in result.all()}
    
    async def get_full_stats(self) -> dict:
        """Get comprehensive statistics."""
        return {
            "total_users": await self.get_total_users(),
            "total_tasks": await self.get_total_tasks(),
            "tasks_by_status": await self.get_tasks_by_status(),
            "total_tokens_spent": await self.get_total_tokens_spent(),
            "tasks_today": await self.get_tasks_today(),
            "users_today": await self.get_users_today(),
            "active_users_today": await self.get_active_users_today(),
            "model_usage": await self.get_model_usage(),
        }


class PaymentRepository:
    """Repository for Payment CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        yookassa_payment_id: str,
        package: str,
        tokens_amount: int,
        amount_value: str,
        confirmation_url: str,
        status: str = "pending",
    ) -> "Payment":
        """Create a new payment record."""
        from bot.db.models import Payment
        
        payment = Payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment_id,
            package=package,
            tokens_amount=tokens_amount,
            amount_value=amount_value,
            confirmation_url=confirmation_url,
            status=status,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        
        return payment
    
    async def get_by_yookassa_id(self, yookassa_payment_id: str) -> Optional["Payment"]:
        """Get payment by YooKassa payment ID."""
        from bot.db.models import Payment
        
        result = await self.session.execute(
            select(Payment).where(Payment.yookassa_payment_id == yookassa_payment_id)
        )
        return result.scalar_one_or_none()
    
    async def get_latest_pending(self, user_id: int) -> Optional["Payment"]:
        """Get user's latest pending payment."""
        from bot.db.models import Payment
        
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .where(Payment.status.in_(["pending", "waiting_for_capture"]))
            .order_by(desc(Payment.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def update_status(
        self,
        payment_id: int,
        status: str,
        paid: bool = False,
    ) -> Optional["Payment"]:
        """Update payment status."""
        from bot.db.models import Payment
        
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if payment is None:
            return None
        
        payment.status = status
        payment.paid = paid
        await self.session.commit()
        await self.session.refresh(payment)
        
        return payment
