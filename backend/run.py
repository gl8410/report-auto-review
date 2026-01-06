import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure the current directory is in sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    uvicorn.run("backend.main:app", host="10.254.68.193", port=8000, reload=True)
