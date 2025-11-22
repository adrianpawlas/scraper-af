"""
SigLIP image embedding processor
"""

import asyncio
from typing import List, Optional, Dict, Any
import torch
from transformers import SiglipProcessor, SiglipModel
from PIL import Image
import requests
from io import BytesIO
from pathlib import Path
import hashlib
from loguru import logger


class SiglipEmbedder:
    """SigLIP model wrapper for generating image embeddings"""

    def __init__(self, model_name: str = "google/siglip-base-patch16-384", device: str = "auto", cache_dir: str = "./cache/embeddings"):
        """
        Initialize SigLIP embedder

        Args:
            model_name: HuggingFace model name
            device: Device to run model on ('auto', 'cpu', 'cuda')
            cache_dir: Directory to cache downloaded images
        """
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Determine device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Initializing SigLIP model on device: {self.device}")

        # Load model and processor
        self.processor = SiglipProcessor.from_pretrained(model_name)
        self.model = SiglipModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

        logger.info(f"SigLIP model loaded: {model_name}")

    def _get_image_cache_path(self, url: str) -> Path:
        """Get cache path for image URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"

    def _download_image(self, url: str) -> Optional[Image.Image]:
        """
        Download image from URL with caching

        Args:
            url: Image URL

        Returns:
            PIL Image or None if failed
        """
        cache_path = self._get_image_cache_path(url)

        # Check cache first
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except Exception as e:
                logger.warning(f"Failed to load cached image {cache_path}: {e}")

        # Download image
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Convert to RGB and save to cache
            image = Image.open(BytesIO(response.content)).convert('RGB')
            image.save(cache_path, 'JPEG', quality=95)

            return image

        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            return None

    def _preprocess_image(self, image: Image.Image) -> torch.Tensor:
        """
        Preprocess image for SigLIP model

        Args:
            image: PIL Image

        Returns:
            Preprocessed tensor
        """
        # Resize image maintaining aspect ratio
        target_size = (self.processor.image_processor.size['height'],
                      self.processor.image_processor.size['width'])

        # Calculate resize dimensions
        width, height = image.size
        aspect_ratio = width / height

        if aspect_ratio > 1:  # wider than tall
            new_width = int(target_size[1] * aspect_ratio)
            new_height = target_size[1]
        else:  # taller than wide
            new_width = target_size[0]
            new_height = int(target_size[0] / aspect_ratio)

        # Resize
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Center crop to target size
        left = (new_width - target_size[1]) // 2
        top = (new_height - target_size[0]) // 2
        right = left + target_size[1]
        bottom = top + target_size[0]

        image = image.crop((left, top, right, bottom))

        # Process with SigLIP processor
        inputs = self.processor(images=image, return_tensors="pt")
        return inputs['pixel_values'].to(self.device)

    @torch.no_grad()
    def generate_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate embedding for image URL

        Args:
            image_url: URL of image to process

        Returns:
            Embedding vector as list of floats, or None if failed
        """
        try:
            # Download image
            image = self._download_image(image_url)
            if image is None:
                return None

            # Preprocess image
            pixel_values = self._preprocess_image(image)

            # Generate embedding
            outputs = self.model(pixel_values=pixel_values)
            embedding = outputs.pooler_output.squeeze().cpu().numpy()

            # Normalize embedding
            embedding = embedding / torch.norm(torch.tensor(embedding))

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate embedding for {image_url}: {e}")
            return None

    async def generate_embeddings_batch(self, image_urls: List[str], max_concurrent: int = 3) -> Dict[str, Optional[List[float]]]:
        """
        Generate embeddings for multiple images concurrently

        Args:
            image_urls: List of image URLs
            max_concurrent: Maximum concurrent downloads/processing

        Returns:
            Dictionary mapping URLs to embeddings
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}

        async def process_single(url: str):
            async with semaphore:
                embedding = await asyncio.get_event_loop().run_in_executor(
                    None, self.generate_embedding, url
                )
                results[url] = embedding

        # Create tasks
        tasks = [process_single(url) for url in image_urls]

        # Run tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for emb in results.values() if emb is not None)
        logger.info(f"Generated embeddings for {successful}/{len(image_urls)} images")

        return results

    def __del__(self):
        """Cleanup model resources"""
        if hasattr(self, 'model'):
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
