"""Progress animation for image generation tasks."""

import asyncio
import random
import time
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


# Красивые мотивационные фразы для разных этапов
PROGRESS_PHRASES = [
    "Ваше видение обретает форму",
    "Магия искусственного интеллекта в действии",
    "Создаю что-то особенное для вас",
    "Пиксель за пикселем рождается шедевр",
    "Превращаю слова в визуальное искусство",
    "Ваша идея материализуется",
    "Нейросеть рисует ваш образ",
    "Творческий процесс в самом разгаре",
    "Скоро увидите результат",
    "Финальные штрихи",
    "Почти готово, осталось совсем чуть-чуть",
    "Добавляю последние детали",
]


# Последовательные надписи для редактирования (меняются по порядку)
EDIT_SUBTITLES = [
    "Изучаю ваше фото",
    "Понимаю что нужно изменить",
    "Применяю изменения",
    "Дорабатываю детали",
    "Финализирую результат",
]


# Последовательные надписи для генерации
GENERATE_SUBTITLES = [
    "Анализирую ваш запрос",
    "Создаю композицию",
    "Прорисовываю детали",
    "Добавляю финальные штрихи",
    "Готовлю результат",
]


class ProgressAnimator:
    """Animated progress bar for generation tasks."""
    
    def __init__(
        self,
        telegram_id: int,
        bot_token: str,
        task_type: str = "generate",
        total_steps: int = 5,
    ):
        """
        Initialize progress animator.
        
        Args:
            telegram_id: User's Telegram ID
            bot_token: Bot token for sending messages
            task_type: "generate" or "edit"
            total_steps: Total number of steps (default 5)
        """
        self.telegram_id = telegram_id
        self.bot_token = bot_token
        self.task_type = task_type
        self.total_steps = total_steps
        
        self.message_id: Optional[int] = None
        self.start_time = time.time()
        self.current_step = 1
        self.current_progress = 0
        self.current_subtitle_index = 0
        self.is_running = False
        self.animation_task: Optional[asyncio.Task] = None
        
        # Task type emoji, title and subtitles
        if task_type == "edit":
            self.emoji = "✏️"
            self.title = "Редактирование"
            self.subtitles = EDIT_SUBTITLES
        else:
            self.emoji = "🎨"
            self.title = "Генерация"
            self.subtitles = GENERATE_SUBTITLES
    
    async def start(self) -> None:
        """Start the progress animation."""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        # Send initial message
        await self._send_initial_message()
        
        # Start animation loop
        self.animation_task = asyncio.create_task(self._animation_loop())
    
    async def stop(self) -> None:
        """Stop the progress animation and delete message."""
        self.is_running = False
        
        # Cancel animation task
        if self.animation_task:
            self.animation_task.cancel()
            try:
                await self.animation_task
            except asyncio.CancelledError:
                pass
        
        # Delete message
        if self.message_id:
            await self._delete_message()
    
    async def _send_initial_message(self) -> None:
        """Send initial progress message."""
        try:
            from aiogram import Bot
            import redis.asyncio as redis
            
            bot = Bot(token=self.bot_token)
            
            text = self._build_progress_text()
            
            message = await bot.send_message(
                chat_id=self.telegram_id,
                text=text,
                parse_mode="HTML",
            )
            
            self.message_id = message.message_id
            
            # Save message_id to Redis for later deletion
            redis_client = redis.from_url("redis://redis:6379/0")
            message_id_key = f"progress_animation:{self.telegram_id}"
            await redis_client.set(message_id_key, str(self.message_id), ex=600)  # Expire in 10 minutes
            await redis_client.close()
            
            await bot.session.close()
            
        except Exception as e:
            logger.error(f"Failed to send initial progress message: {e}")
    
    async def _animation_loop(self) -> None:
        """Main animation loop that updates progress periodically."""
        try:
            while self.is_running:
                # Random delay between 7-12 seconds
                delay = random.uniform(7, 12)
                await asyncio.sleep(delay)
                
                if not self.is_running:
                    break
                
                # Update progress
                await self._update_progress()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in animation loop: {e}")
    
    async def _update_progress(self) -> None:
        """Update progress message with new values."""
        if not self.message_id:
            return
        
        try:
            from aiogram import Bot
            
            bot = Bot(token=self.bot_token)
            
            # Increment progress (10-20% each time)
            progress_increment = random.randint(10, 20)
            self.current_progress = min(95, self.current_progress + progress_increment)
            
            # Maybe increment step
            expected_step = int((self.current_progress / 100) * self.total_steps) + 1
            if expected_step > self.current_step and expected_step <= self.total_steps:
                self.current_step = expected_step
            
            # Move to next subtitle if available
            if self.current_subtitle_index < len(self.subtitles) - 1:
                self.current_subtitle_index += 1
            
            text = self._build_progress_text()
            
            await bot.edit_message_text(
                chat_id=self.telegram_id,
                message_id=self.message_id,
                text=text,
                parse_mode="HTML",
            )
            
            await bot.session.close()
            
        except Exception as e:
            logger.error(f"Failed to update progress message: {e}")
    
    def _build_progress_text(self) -> str:
        """Build progress message text."""
        # Calculate elapsed time
        elapsed = int(time.time() - self.start_time)
        
        # Build progress bar
        total_blocks = 10
        filled_blocks = int((self.current_progress / 100) * total_blocks)
        empty_blocks = total_blocks - filled_blocks
        
        progress_bar = "🟩" * filled_blocks + "⬜" * empty_blocks
        
        # Get current subtitle
        subtitle = self.subtitles[self.current_subtitle_index]
        
        # Random motivational phrase
        phrase = random.choice(PROGRESS_PHRASES)
        
        text = (
            f"{self.emoji} <b>{self.title}</b>\n\n"
            f"{subtitle}\n\n"
            f"{progress_bar} {self.current_progress}%\n\n"
            f"⏱ Прошло: {elapsed}с • Шаг {self.current_step}/{self.total_steps}\n\n"
            f"<i>{phrase}</i>"
        )
        
        return text
    
    async def _delete_message(self) -> None:
        """Delete the progress message."""
        if not self.message_id:
            return
        
        try:
            from aiogram import Bot
            import redis.asyncio as redis
            
            bot = Bot(token=self.bot_token)
            
            await bot.delete_message(
                chat_id=self.telegram_id,
                message_id=self.message_id,
            )
            
            await bot.session.close()
            
            # Clean up Redis key
            redis_client = redis.from_url("redis://redis:6379/0")
            message_id_key = f"progress_animation:{self.telegram_id}"
            await redis_client.delete(message_id_key)
            await redis_client.close()
            
        except Exception as e:
            logger.error(f"Failed to delete progress message: {e}")


async def stop_progress_animation(telegram_id: int, bot_token: str) -> None:
    """
    Stop and delete any progress animation for a user.
    
    This is a helper function to stop animation from worker without needing the animator instance.
    It finds and deletes any message with progress animation text.
    
    Args:
        telegram_id: User's Telegram ID
        bot_token: Bot token
    """
    try:
        from aiogram import Bot
        
        bot = Bot(token=bot_token)
        
        # Get recent messages and try to delete progress animation
        # We can't easily find the exact message, so we'll just let it auto-delete on result send
        # The animation will be replaced by the result message
        
        await bot.session.close()
        
    except Exception as e:
        logger.error(f"Failed to stop progress animation: {e}")


async def delete_progress_animation_for_user(telegram_id: int, bot_token: str) -> None:
    """
    Delete progress animation message for a user using Redis to find message_id.
    
    Args:
        telegram_id: User's Telegram ID
        bot_token: Bot token
    """
    try:
        import redis.asyncio as redis
        from aiogram import Bot
        
        # Get message_id from Redis
        redis_client = redis.from_url("redis://redis:6379/0")
        message_id_key = f"progress_animation:{telegram_id}"
        message_id = await redis_client.get(message_id_key)
        
        if message_id:
            message_id = int(message_id.decode())
            
            # Delete the message
            bot = Bot(token=bot_token)
            try:
                await bot.delete_message(chat_id=telegram_id, message_id=message_id)
                logger.info(f"Deleted progress animation message {message_id} for user {telegram_id}")
            except Exception as e:
                logger.debug(f"Could not delete progress message {message_id}: {e}")
            finally:
                await bot.session.close()
            
            # Clean up Redis key
            await redis_client.delete(message_id_key)
        
        await redis_client.close()
        
    except Exception as e:
        logger.warning(f"Failed to delete progress animation for user {telegram_id}: {e}")
