"""Image provider service for AI image generation."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of an image generation/edit operation."""
    
    success: bool
    image_url: Optional[str] = None
    error: Optional[str] = None


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, model: str = None) -> GenerationResult:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use (optional, uses default if not specified)
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        pass
    
    @abstractmethod
    async def edit(self, image_source: str, prompt: str, bot_token: str = None, model: str = None) -> GenerationResult:
        """
        Edit an existing image based on a text prompt.
        
        Args:
            image_source: URL or Telegram file_id of the source image
            prompt: Text description of the desired changes
            bot_token: Telegram bot token (required if image_source is file_id)
            model: Model to use (optional, uses default if not specified)
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        pass


# Available models for generation
AVAILABLE_MODELS = {
    "gpt-image-1": "GPT Image 1 (Стандартная)",
    "gpt-image-1.5": "GPT Image 1.5 (Улучшенная)",
}

DEFAULT_MODEL = "gpt-image-1"


class OpenAIImageProvider(ImageProvider):
    """OpenAI Images API implementation of ImageProvider."""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        """
        Initialize OpenAI image provider.
        
        Args:
            api_key: OpenAI API key
            model: Model to use for generation (default: gpt-image-1)
        """
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate(self, prompt: str, model: str = None) -> GenerationResult:
        """
        Generate an image using OpenAI Images API.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use (optional, uses instance default if not specified)
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        use_model = model or self.model
        logger.info(f"Generating image with model {use_model}, prompt: {prompt[:100]}...")
        
        try:
            response = await self.client.images.generate(
                model=use_model,
                prompt=prompt,
                n=1,
                size="1024x1024",
            )
            
            image_url = response.data[0].url
            logger.info(f"Image generated successfully: {image_url}")
            
            return GenerationResult(
                success=True,
                image_url=image_url,
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Image generation failed: {error_msg}")
            
            return GenerationResult(
                success=False,
                error=error_msg,
            )
    
    async def edit(self, image_source: str, prompt: str, bot_token: str = None, model: str = None) -> GenerationResult:
        """
        Edit an image using OpenAI Images API.
        
        Args:
            image_source: URL or Telegram file_id of the source image
            prompt: Text description of the desired changes
            bot_token: Telegram bot token (required if image_source is file_id)
            model: Model to use (optional, uses instance default if not specified)
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        use_model = model or self.model
        logger.info(f"Editing image {image_source} with model {use_model}, prompt: {prompt[:100]}...")
        
        try:
            import httpx
            import io
            
            image_data: bytes
            file_extension = "png"  # Default extension
            
            # Check if image_source is a URL or Telegram file_id
            if image_source.startswith(('http://', 'https://')):
                # It's a URL - download directly
                async with httpx.AsyncClient() as http_client:
                    img_response = await http_client.get(image_source)
                    img_response.raise_for_status()
                    image_data = img_response.content
                    
                    # Try to get extension from URL
                    if '.jpg' in image_source or '.jpeg' in image_source:
                        file_extension = "jpg"
                    elif '.webp' in image_source:
                        file_extension = "webp"
            else:
                # It's a Telegram file_id - download from Telegram
                if not bot_token:
                    raise ValueError("bot_token required for Telegram file_id")
                
                from aiogram import Bot
                
                bot = Bot(token=bot_token)
                
                try:
                    # Get file info
                    file = await bot.get_file(image_source)
                    
                    # Get extension from file path
                    if file.file_path:
                        if file.file_path.endswith('.jpg') or file.file_path.endswith('.jpeg'):
                            file_extension = "jpg"
                        elif file.file_path.endswith('.webp'):
                            file_extension = "webp"
                        elif file.file_path.endswith('.png'):
                            file_extension = "png"
                    
                    # Download file
                    file_bytes = io.BytesIO()
                    await bot.download_file(file.file_path, file_bytes)
                    image_data = file_bytes.getvalue()
                    
                    logger.info(f"Downloaded image from Telegram: {len(image_data)} bytes, extension: {file_extension}")
                finally:
                    await bot.session.close()
            
            # Determine MIME type
            mime_types = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg", 
                "png": "image/png",
                "webp": "image/webp",
            }
            mime_type = mime_types.get(file_extension, "image/png")
            
            # Create file tuple for OpenAI API: (filename, content, mime_type)
            image_file = (f"image.{file_extension}", image_data, mime_type)
            
            logger.info(f"Sending to OpenAI with MIME type: {mime_type}")
            
            # Use OpenAI edit endpoint
            response = await self.client.images.edit(
                model=use_model,
                image=image_file,
                prompt=prompt,
                n=1,
                size="1024x1024",
            )
            
            result_url = response.data[0].url
            logger.info(f"Image edited successfully: {result_url}")
            
            return GenerationResult(
                success=True,
                image_url=result_url,
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Image edit failed: {error_msg}")
            
            return GenerationResult(
                success=False,
                error=error_msg,
            )
