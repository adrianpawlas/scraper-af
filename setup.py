"""
Setup script to verify all dependencies are installed correctly
"""
import sys
import subprocess

def check_package(package_name, import_name=None):
    """Check if a package is installed"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"✅ {package_name} is installed")
        return True
    except ImportError:
        print(f"❌ {package_name} is NOT installed")
        return False

def main():
    """Check all required packages"""
    print("Checking dependencies...\n")
    
    packages = [
        ("playwright", "playwright"),
        ("beautifulsoup4", "bs4"),
        ("requests", "requests"),
        ("supabase", "supabase"),
        ("transformers", "transformers"),
        ("torch", "torch"),
        ("pillow", "PIL"),
        ("python-dotenv", "dotenv"),
        ("tqdm", "tqdm"),
        ("lxml", "lxml"),
    ]
    
    all_installed = True
    for package, import_name in packages:
        if not check_package(package, import_name):
            all_installed = False
    
    print("\n" + "="*60)
    if all_installed:
        print("✅ All dependencies are installed!")
        print("\nNext steps:")
        print("1. Install Playwright browsers: playwright install chromium")
        print("2. Run test: python test_scraper.py")
        print("3. Run scraper: python main.py")
    else:
        print("❌ Some dependencies are missing!")
        print("\nInstall missing packages with:")
        print("pip install -r requirements.txt")
        print("\nThen install Playwright browsers:")
        print("playwright install chromium")
    print("="*60)

if __name__ == "__main__":
    main()

