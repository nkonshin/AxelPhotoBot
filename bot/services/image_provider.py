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
    async def generate(self, prompt: str) -> GenerationResult:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        pass
    
    @abstractmethod
    async def edit(self, image_url: str, prompt: str) -> GenerationResult:
        """
        Edit an existing image based on a text prompt.
        
        Args:
            image_url: URL of the source image to edit
            prompt: Text description of the desired changes
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        pass


class OpenAIImageProvider(ImageProvider):
    """OpenAI Images API implementation of ImageProvider."""
    
    def __init__(self, api_key: str, model: str = "gpt-image-1"):
        """
        Initialize OpenAI image provider.
        
        Args:
            api_key: OpenAI API key
            model: Model to use for generation (default: gpt-image-1)
        """
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate(self, prompt: str) -> GenerationResult:
        """
        Generate an image using OpenAI Images API.
        
        Args:
            prompt: Text description of the image to generate
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        logger.info(f"Generating image with prompt: {prompt[:100]}...")
        
        try:
            response = await self.client.images.generate(
                model=self.model,
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
    
    async def edit(self, image_url: str, prompt: str) -> GenerationResult:
        """
        Edit an image using OpenAI Images API.
        
        Args:
            image_url: URL of the source image to edit
            prompt: Text description of the desired changes
        
        Returns:
            GenerationResult with success status and image URL or error
        """
        logger.info(f"Editing image {image_url} with prompt: {prompt[:100]}...")
        
        try:
            # Download the source image first
            import httpx
            
            async with httpx.AsyncClient() as http_client:
                img_response = await http_client.get(image_url)
                img_response.raise_for_status()
                image_data = img_response.content
            
            # Use OpenAI edit endpoint
            response = await self.client.images.edit(
                model=self.model,
                image=image_data,
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
