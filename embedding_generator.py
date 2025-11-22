"""
Image embedding generator using SigLIP model
"""
import torch
from transformers import AutoProcessor, AutoModel
from PIL import Image
import requests
from io import BytesIO
import logging
from typing import List, Optional, Dict
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
                # Try multiple approaches to download images

                # Approach 1: Use browser to navigate to image URL directly
                try:
                    logger.debug(f"Trying browser navigation approach for {image_url}")
                    # Create a new page for image download
                    image_page = await self.browser_page.context.new_page()
                    await image_page.goto(image_url, wait_until="load", timeout=10000)

                    # Try to get image data from the page
                    image_buffer = await image_page.evaluate("""
                        () => {
                            // If it's a direct image URL, try to get the image data
                            if (document.body && document.body.children.length === 0) {
                                // Likely a direct image response
                                const canvas = document.createElement('canvas');
                                const ctx = canvas.getContext('2d');
                                const img = new Image();
                                img.crossOrigin = 'anonymous';
                                return new Promise((resolve) => {
                                    img.onload = () => {
                                        canvas.width = img.width;
                                        canvas.height = img.height;
                                        ctx.drawImage(img, 0, 0);
                                        resolve(canvas.toDataURL('image/png').split(',')[1]);
                                    };
                                    img.onerror = () => resolve(null);
                                    img.src = window.location.href;
                                });
                            }
                            return null;
                        }
                    """)

                    await image_page.close()

                    if image_buffer:
                        import base64
                        image_bytes = base64.b64decode(image_buffer)
                        image = Image.open(BytesIO(image_bytes))
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        logger.debug("Browser navigation approach succeeded")
                        return image

                except Exception as e:
                    logger.debug(f"Browser navigation approach failed: {e}")

                # Approach 2: Browser cookies with enhanced headers
                try:
                    logger.debug(f"Trying browser cookies approach for {image_url}")
                    cookies = await self.browser_page.context.cookies()
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

                    response = requests.get(image_url, timeout=30, headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Referer': 'https://www.abercrombie.com/shop/eu/mens-bottoms--1',
                        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        'Sec-Ch-Ua-Mobile': '?0',
                        'Sec-Ch-Ua-Platform': '"Linux"',
                        'Sec-Fetch-Dest': 'image',
                        'Sec-Fetch-Mode': 'no-cors',
                        'Sec-Fetch-Site': 'cross-site',
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }, cookies=cookie_dict, stream=True)

                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content))
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    logger.debug("Browser cookies approach succeeded")
                    return image

                except Exception as e:
                    logger.debug(f"Browser cookies approach failed: {e}")

                # Approach 3: Try different image size/format
                try:
                    logger.debug(f"Trying alternative image URL for {image_url}")
                    # Try without _prod1 suffix or with different format
                    alt_urls = [
                        image_url.replace('_prod1', '_model1'),
                        image_url.replace('_prod1', ''),
                        image_url.replace('anf.scene7.com', 'images.abercrombie.com')
                    ]

                    for alt_url in alt_urls:
                        try:
                            response = requests.get(alt_url, timeout=15, headers={
                                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                                'Accept': 'image/*'
                            }, stream=True)
                            if response.status_code == 200:
                                image = Image.open(BytesIO(response.content))
                                if image.mode != 'RGB':
                                    image = image.convert('RGB')
                                logger.debug(f"Alternative URL approach succeeded: {alt_url}")
                                return image
                        except:
                            continue

                except Exception as e:
                    logger.debug(f"Alternative URL approach failed: {e}")

                logger.warning(f"All image download approaches failed for {image_url}")
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
    
    async def generate_embedding_from_text(self, product_data: Dict) -> Optional[List[float]]:
        """
        Generate 768-dimensional embedding from product text data using SigLIP

        Args:
            product_data: Dictionary containing product information

        Returns:
            List of 768 floats representing the embedding, or None if failed
        """
        try:
            # Create rich text representation from product data
            text_parts = []

            if product_data.get('title'):
                text_parts.append(f"Title: {product_data['title']}")

            if product_data.get('description'):
                text_parts.append(f"Description: {product_data['description']}")

            if product_data.get('category'):
                text_parts.append(f"Category: {product_data['category']}")

            if product_data.get('gender'):
                text_parts.append(f"Gender: {product_data['gender']}")

            if product_data.get('brand'):
                text_parts.append(f"Brand: {product_data['brand']}")

            # Combine all text
            text = ". ".join(text_parts)
            if not text or len(text.strip()) < 10:
                logger.warning(f"Insufficient text for embedding: {text[:50]}...")
                return None

            logger.debug(f"Generating text embedding for: {text[:100]}...")

            # Process text - SigLIP can handle text inputs
            inputs = self.processor(text=[text], return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                # Try different methods to get text embeddings from SigLIP
                if hasattr(self.model, 'get_text_features'):
                    outputs = self.model.get_text_features(**inputs)
                else:
                    # Fallback: use forward pass
                    outputs = self.model(**inputs)
                    if hasattr(outputs, 'text_embeds'):
                        outputs = outputs.text_embeds
                    elif hasattr(outputs, 'pooler_output'):
                        outputs = outputs.pooler_output
                    elif hasattr(outputs, 'last_hidden_state'):
                        # Mean pool across sequence dimension
                        outputs = outputs.last_hidden_state.mean(dim=1)
                    else:
                        logger.error(f"Unexpected model output structure: {type(outputs)}")
                        return None

                # Ensure we have the right shape
                embedding = outputs.squeeze()
                if len(embedding.shape) > 1:
                    embedding = embedding.mean(dim=0)  # Average across sequence if needed

                embedding = embedding.cpu().numpy()

                # Normalize the embedding
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate text embedding: {e}")
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

