import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure the current directory is in sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from app.core.config import settings

    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.BACKEND_PORT, reload=True, log_level="warning")
