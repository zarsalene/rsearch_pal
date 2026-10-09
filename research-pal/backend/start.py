"""Entry file for a Hugging Face Gradio Space (free). It starts the FastAPI app on port 7860."""
import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    os.environ.setdefault("DATA_DIR", "/tmp/data")
    uvicorn.run(app, host="0.0.0.0", port=7860)
