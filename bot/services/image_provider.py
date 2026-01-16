"""Image provider service for AI image generation."""

import base64
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
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    error: Optional[str] = None


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str = None,
        quality: str | None = None,
        size: str | None = None,
    ) -> GenerationResult:
        pass
    
    @abstractmethod
    async def edit(
        self,
        image_source: str,
        prompt: str,
        bot_token: str = None,
        model: str = None,
        quality: str | None = None,
        size: str | None = None,
    ) -> GenerationResult:
        pass


# Available models for generation and editing
# gpt-image-1: Standard GPT image model
# gpt-image-1.5: Improved GPT image model
# seedream-4-5: BytePlus SeeDream 4.5 model
AVAILABLE_MODELS = {
    "gpt-image-1": "GPT Image 1 (Стандартная)",
    "gpt-image-1.5": "GPT Image 1.5 (Улучшенная)",
    "seedream-4-5": "SeeDream 4.5 (Новейшая)",
}

DEFAULT_MODEL = "gpt-image-1"


class OpenAIImageProvider(ImageProvider):
    """OpenAI Images API implementation of ImageProvider."""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate(
        self,
        prompt: str,
        model: str = None,
        quality: str | None = None,
        size: str | None = None,
    ) -> GenerationResult:
        """
        Generate an image using OpenAI Images API.
        GPT image models always return base64.
        """
        use_model = model or self.model
        logger.info(f"Generating image with model {use_model}, prompt: {prompt[:100]}...")
        
        try:
            # GPT image models don't support response_format parameter
            # They always return b64_json
            response = await self.client.images.generate(
                model=use_model,
                prompt=prompt,
                n=1,
                quality=quality or "auto",
                size=size or "auto",
            )
            
            image_data = response.data[0]
            
            # GPT image models return b64_json
            if hasattr(image_data, 'b64_json') and image_data.b64_json:
                logger.info(f"Image generated successfully (base64)")
                return GenerationResult(
                    success=True,
                    image_base64=image_data.b64_json,
                )
            # DALL-E models may return URL
            elif hasattr(image_data, 'url') and image_data.url:
                logger.info(f"Image generated successfully (URL)")
                return GenerationResult(
                    success=True,
                    image_url=image_data.url,
                )
            else:
                logger.error(f"OpenAI returned empty response. Data: {image_data}")
                return GenerationResult(
                    success=False,
                    error="OpenAI не вернул изображение",
                )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Image generation failed: {error_msg}")
            return GenerationResult(
                success=False,
                error=error_msg,
            )
    
    async def edit(
        self,
        image_source: str,
        prompt: str,
        bot_token: str = None,
        model: str = None,
        quality: str | None = None,
        size: str | None = None,
    ) -> GenerationResult:
        """
        Edit an image using OpenAI Images API.
        Supports: gpt-image-1, gpt-image-1.5, dall-e-2
        
        image_source can be:
        - A single file_id or URL
        - A JSON array of file_ids (for multiple images)
        """
        use_model = model or self.model
        
        logger.info(f"Editing image with model {use_model}, prompt: {prompt[:100]}...")
        
        try:
            import httpx
            import io
            import json
            
            # Parse image_source - could be single file_id or JSON array
            image_sources = []
            try:
                parsed = json.loads(image_source)
                if isinstance(parsed, list):
                    image_sources = parsed
                else:
                    image_sources = [image_source]
            except (json.JSONDecodeError, TypeError):
                image_sources = [image_source]
            
            # Download all images
            image_files = []
            
            for idx, src in enumerate(image_sources):
                image_bytes: bytes
                
                if src.startswith(('http://', 'https://')):
                    # It's a URL - download directly
                    async with httpx.AsyncClient() as http_client:
                        img_response = await http_client.get(src)
                        img_response.raise_for_status()
                        image_bytes = img_response.content
                else:
                    # It's a Telegram file_id - download from Telegram
                    if not bot_token:
                        raise ValueError("bot_token required for Telegram file_id")
                    
                    from aiogram import Bot
                    
                    bot = Bot(token=bot_token)
                    
                    try:
                        file = await bot.get_file(src)
                        file_buffer = io.BytesIO()
                        await bot.download_file(file.file_path, file_buffer)
                        image_bytes = file_buffer.getvalue()
                        logger.info(f"Downloaded image {idx + 1} from Telegram: {len(image_bytes)} bytes")
                    finally:
                        await bot.session.close()
                
                # Create file-like object
                image_file = io.BytesIO(image_bytes)
                image_file.name = f"image_{idx}.png"
                image_files.append(image_file)
            
            logger.info(f"Sending {len(image_files)} image(s) to OpenAI edit endpoint")
            
            # GPT Image models support up to 16 images for editing
            # Pass array of images if multiple, single image otherwise
            image_param = image_files if len(image_files) > 1 else image_files[0]
            
            response = await self.client.images.edit(
                model=use_model,
                image=image_param,
                prompt=prompt,
                n=1,
                quality=quality or "auto",
                size=size or "auto",
            )
            
            image_data = response.data[0]
            
            # GPT image models return b64_json
            if hasattr(image_data, 'b64_json') and image_data.b64_json:
                logger.info(f"Image edited successfully (base64)")
                return GenerationResult(
                    success=True,
                    image_base64=image_data.b64_json,
                )
            # DALL-E 2 may return URL
            elif hasattr(image_data, 'url') and image_data.url:
                logger.info(f"Image edited successfully (URL)")
                return GenerationResult(
                    success=True,
                    image_url=image_data.url,
                )
            else:
                logger.error(f"OpenAI edit returned empty response")
                return GenerationResult(
                    success=False,
                    error="OpenAI не вернул изображение",
                )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Image edit failed: {error_msg}")
            return GenerationResult(
                success=False,
                error=error_msg,
            )


class SeeDreamImageProvider(ImageProvider):
    """BytePlus ARK SeeDream 4.5 implementation of ImageProvider."""

    # Size mapping from OpenAI format to SeeDream format
    SIZE_MAPPING = {
        "1024x1024": "2K",
        "1024x1536": "2K",
        "1536x1024": "2K",
    }

    def __init__(self, api_key: str, model: str = "seedream-4-5-251128"):
        self.api_key = api_key
        self.model = model
        # SeeDream uses OpenAI SDK with custom base_url
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        )

    def _map_size(self, size: str | None) -> str:
        """Map OpenAI size format to SeeDream format."""
        if size and size in self.SIZE_MAPPING:
            return self.SIZE_MAPPING[size]
        return "2K"  # Default to 2K

    async def generate(
        self,
        prompt: str,
        model: str = None,
        quality: str | None = None,
        size: str | None = None,
    ) -> GenerationResult:
        """
        Generate an image using SeeDream API.
        SeeDream returns URLs, not base64.
        """
        use_model = model or self.model
        seedream_size = self._map_size(size)

        logger.info(f"Generating image with SeeDream {use_model}, size: {seedream_size}, prompt: {prompt[:100]}...")

        try:
            # SeeDream supports response_format="url"
            response = await self.client.images.generate(
                model=use_model,
                prompt=prompt,
                n=1,
                size=seedream_size,
                response_format="url",
                extra_body={
                    "watermark": False,  # Disable watermark by default
                }
            )

            image_data = response.data[0]

            # SeeDream returns URL
            if hasattr(image_data, 'url') and image_data.url:
                logger.info(f"Image generated successfully with SeeDream (URL)")
                return GenerationResult(
                    success=True,
                    image_url=image_data.url,
                )
            else:
                logger.error(f"SeeDream returned empty response. Data: {image_data}")
                return GenerationResult(
                    success=False,
                    error="SeeDream не вернул изображение",
                )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"SeeDream image generation failed: {error_msg}")
            return GenerationResult(
                success=False,
                error=error_msg,
            )

    async def edit(
        self,
        image_source: str,
        prompt: str,
        bot_token: str = None,
        model: str = None,
        quality: str | None = None,
        size: str | None = None,
    ) -> GenerationResult:
        """
        Edit an image using SeeDream API.

        image_source can be:
        - A single file_id or URL
        - A JSON array of file_ids (for multiple images)
        """
        use_model = model or self.model
        seedream_size = self._map_size(size)

        logger.info(f"Editing image with SeeDream {use_model}, size: {seedream_size}, prompt: {prompt[:100]}...")

        try:
            import httpx
            import io
            import json

            # Parse image_source - could be single file_id or JSON array
            image_sources = []
            try:
                parsed = json.loads(image_source)
                if isinstance(parsed, list):
                    image_sources = parsed
                else:
                    image_sources = [image_source]
            except (json.JSONDecodeError, TypeError):
                image_sources = [image_source]

            # For SeeDream, we need to get the image URL
            # If it's a Telegram file_id, download and upload it first
            image_url = None

            # Use first image for edit (SeeDream might support only one)
            src = image_sources[0]

            if src.startswith(('http://', 'https://')):
                # It's already a URL - use directly
                image_url = src
            else:
                # It's a Telegram file_id - need to get URL
                # For now, we'll download and send as file
                if not bot_token:
                    raise ValueError("bot_token required for Telegram file_id")

                from aiogram import Bot

                bot = Bot(token=bot_token)

                try:
                    file = await bot.get_file(src)
                    # Get direct Telegram URL
                    image_url = f"https://api.telegram.org/file/bot{bot_token}/{file.file_path}"
                    logger.info(f"Got Telegram image URL: {image_url}")
                finally:
                    await bot.session.close()

            logger.info(f"Sending edit request to SeeDream with image URL")

            # SeeDream uses extra_body for image parameter in edit
            response = await self.client.images.generate(
                model=use_model,
                prompt=prompt,
                n=1,
                size=seedream_size,
                response_format="url",
                extra_body={
                    "image": image_url,
                    "watermark": False,
                }
            )

            image_data = response.data[0]

            # SeeDream returns URL
            if hasattr(image_data, 'url') and image_data.url:
                logger.info(f"Image edited successfully with SeeDream (URL)")
                return GenerationResult(
                    success=True,
                    image_url=image_data.url,
                )
            else:
                logger.error(f"SeeDream edit returned empty response")
                return GenerationResult(
                    success=False,
                    error="SeeDream не вернул изображение",
                )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"SeeDream image edit failed: {error_msg}")
            return GenerationResult(
                success=False,
                error=error_msg,
            )
