# Entry point for Railpack deployment
from app.main import app

# Expose app for uvicorn
__all__ = ["app"]
