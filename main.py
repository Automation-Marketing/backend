from fastapi import FastAPI
import requests
from routes.brand import router as brand_router
from routes.campaign import router as campaign_router

app = FastAPI()

# Register routers
app.include_router(brand_router)
app.include_router(campaign_router)

OLLAMA_URL = "http://host.docker.internal:11434/api/generate"

@app.get("/")
def read_root():
    return {"message": "Backend is running"}

@app.get("/test-llm")
def test_llm():
    payload = {
        "model": "llama3",
        "prompt": "Say hello in one sentence.",
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    return response.json()
