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
    
    def __init__(self, model_name: str = "google/siglip-base-patch16-384"):
        """
        Initialize the embedding generator
        
        Args:
            model_name: HuggingFace model identifier
        """
        logger.info(f"Loading SigLIP model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        
        logger.info("Model loaded successfully")
    
    def download_image(self, image_url: str) -> Optional[Image.Image]:
        """
        Download image from URL
        
        Args:
            image_url: URL of the image
            
        Returns:
            PIL Image object or None if download fails
        """
        try:
            response = requests.get(image_url, timeout=30, stream=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return image
        except Exception as e:
            logger.error(f"Failed to download image from {image_url}: {e}")
            return None
    
    def generate_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate 768-dimensional embedding from image URL
        
        Args:
            image_url: URL of the product image
            
        Returns:
            List of 768 floats representing the embedding, or None if failed
        """
        try:
            # Download image
            image = self.download_image(image_url)
            if image is None:
                return None
            
            # Process image
            inputs = self.processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate embedding
            with torch.no_grad():
                outputs = self.model.get_image_features(**inputs)
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

