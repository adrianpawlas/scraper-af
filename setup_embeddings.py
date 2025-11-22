#!/usr/bin/env python3
"""
Setup script for fixing torch/torchvision version conflicts for embeddings
"""

import subprocess
import sys


def run_command(cmd):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {cmd}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {cmd}")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Fix torch/torchvision versions for SigLIP compatibility"""
    print("🔧 Fixing torch/torchvision versions for SigLIP embeddings...")
    print()

    # Uninstall conflicting versions
    print("Removing conflicting torch/torchvision versions...")
    run_command("pip uninstall torch torchvision torchaudio -y")

    # Install compatible versions
    print("Installing compatible versions...")
    success = run_command("pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121")

    if not success:
        print("CUDA version failed, trying CPU version...")
        success = run_command("pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu")

    if success:
        # Reinstall transformers with compatible version
        print("Installing compatible transformers version...")
        run_command("pip install transformers==4.35.0")

        print()
        print("🎉 Embedding dependencies fixed!")
        print("You can now run the scraper with full embedding support.")
        print()
        print("Test embeddings with:")
        print("python -c \"from src.embeddings.siglip_processor import SiglipEmbedder; print('Embeddings working!')\"")
    else:
        print()
        print("❌ Failed to fix torch/torchvision versions.")
        print("You may need to manually resolve version conflicts.")
        print("The scraper will still work without embeddings.")


if __name__ == "__main__":
    main()
