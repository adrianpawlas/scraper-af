"""
Image embedding generator using SigLIP model
"""
import torch
from transformers import AutoProcessor, AutoModel
from PIL import Image
import requests
from io import BytesIO
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate 768-dimensional embeddings from product images using SigLIP"""
    
    def __init__(self, model_name: str = "google/siglip-base-patch16-384", browser_page=None):
        """
        Initialize the embedding generator

        Args:
            model_name: HuggingFace model identifier
            browser_page: Playwright page object for image downloads (optional)
        """
        logger.info(f"Loading SigLIP model: {model_name}")
        self.browser_page = browser_page
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        # Use AutoProcessor for SigLIP models (works for vision-language models)
        try:
            self.processor = AutoProcessor.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
        except Exception as e:
            logger.error(f"Failed to load SigLIP model with AutoProcessor: {e}")
            # Fallback: try SiglipImageProcessor if available
            try:
                from transformers import SiglipImageProcessor, SiglipModel
                logger.info("Trying SiglipImageProcessor...")
                self.processor = SiglipImageProcessor.from_pretrained(model_name)
                self.model = SiglipModel.from_pretrained(model_name)
            except Exception as e2:
                logger.error(f"Failed to load with SiglipImageProcessor: {e2}")
                raise RuntimeError(f"Could not load SigLIP model {model_name}. Please ensure transformers>=4.37.0 is installed.")
        
        self.model.to(self.device)
        self.model.eval()
        
        logger.info("Model loaded successfully")
    
    async def download_image(self, image_url: str) -> Optional[Image.Image]:
        """
        Download image from URL using browser context if available

        Args:
            image_url: URL of the image

        Returns:
            PIL Image object or None if download fails
        """
        try:
            # Use browser context if available (bypasses anti-bot protection)
            if self.browser_page:
                logger.debug(f"Downloading image via browser: {image_url}")
                # Use browser to get cookies and then download with requests
                try:
                    # Get cookies from browser session
                    cookies = await self.browser_page.context.cookies()
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

                    # Use requests with browser cookies and proper headers
                    response = requests.get(image_url, timeout=30, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'image/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Referer': 'https://www.abercrombie.com/',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'image',
                        'Sec-Fetch-Mode': 'no-cors',
                        'Sec-Fetch-Site': 'cross-site'
                    }, cookies=cookie_dict, stream=True)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content))
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    return image
                except Exception as e:
                    logger.warning(f"Browser cookie approach failed: {e}")
                    return None

                if image_data:
                    # Convert base64 back to bytes and create PIL image
                    import base64
                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(BytesIO(image_bytes))
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    return image
                else:
                    logger.warning(f"Browser fetch failed for {image_url}")
                    return None
            else:
                # Fallback to direct requests with better headers
                logger.debug(f"Downloading image via requests: {image_url}")
                response = requests.get(image_url, timeout=30, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'image/*,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://www.abercrombie.com/',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }, stream=True)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                return image
        except Exception as e:
            logger.error(f"Failed to download image from {image_url}: {e}")
            return None
    
    async def generate_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate 768-dimensional embedding from image URL
        
        Args:
            image_url: URL of the product image
            
        Returns:
            List of 768 floats representing the embedding, or None if failed
        """
        try:
            # Download image
            image = await self.download_image(image_url)
            if image is None:
                return None
            
            # Process image - AutoProcessor for SigLIP returns pixel_values
            processed = self.processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in processed.items()}
            
            # Generate embedding - SigLIP models use get_image_features
            with torch.no_grad():
                if hasattr(self.model, 'get_image_features'):
                    outputs = self.model.get_image_features(**inputs)
                else:
                    # Fallback: try forward pass and extract image features
                    outputs = self.model(**inputs)
                    if hasattr(outputs, 'image_embeds'):
                        outputs = outputs.image_embeds
                    elif isinstance(outputs, tuple):
                        outputs = outputs[0]
                    else:
                        outputs = outputs
                # Get the embedding tensor
                embedding = outputs[0].cpu().numpy()
                
                # Normalize the embedding (L2 normalization)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                
                # Flatten if needed
                embedding = embedding.flatten()
            
            # Convert to list of floats
            embedding_list = embedding.tolist()
            
            # Verify dimension
            if len(embedding_list) != 768:
                logger.warning(f"Expected 768 dimensions, got {len(embedding_list)}. Model output shape: {outputs.shape}")
                # If dimension doesn't match, we might need to use a different method
                # For now, return what we have or pad/truncate
                if len(embedding_list) < 768:
                    # Pad with zeros (shouldn't happen, but safety)
                    embedding_list.extend([0.0] * (768 - len(embedding_list)))
                elif len(embedding_list) > 768:
                    # Truncate (shouldn't happen, but safety)
                    embedding_list = embedding_list[:768]
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"Failed to generate embedding for {image_url}: {e}", exc_info=True)
            return None
    
    def generate_embeddings_batch(self, image_urls: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple images
        
        Args:
            image_urls: List of image URLs
            
        Returns:
            List of embeddings (or None for failed ones)
        """
        embeddings = []
        for url in image_urls:
            embedding = self.generate_embedding(url)
            embeddings.append(embedding)
        return embeddings

