import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL     = os.environ.get('DATABASE_URL')
    SECRET_KEY       = os.environ.get('SECRET_KEY', 'dev-secret-key')
    UPLOAD_FOLDER    = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_IMAGE_SIZE   = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}