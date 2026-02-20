from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import asyncio
import os
import requests

# Import our services
from services.company_resolver import CompanyResolver
from services.scraping_orchestrator import ScrapingOrchestrator
from services.text_processor import TextProcessor
from services.vector_db import VectorDB

# Import routers
from routes.brand import router as brand_router
from routes.campaign import router as campaign_router
from routes.publish import router as publish_router

app = FastAPI(title="Social Media Marketing Automation API")

# Register routers
app.include_router(brand_router)
app.include_router(campaign_router)
app.include_router(publish_router)

OLLAMA_URL = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434/api/generate")

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


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
company_resolver = CompanyResolver()
text_processor = TextProcessor()
vector_db = VectorDB()


class ScrapeCompanyRequest(BaseModel):
    company_name: str
    instagram_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None


class SearchRequest(BaseModel):
    company_name: str
    query: str
    top_k: int = 5
    platform_filter: Optional[str] = None


@app.post("/api/scrape-company")
async def scrape_company(request: ScrapeCompanyRequest):
    """
    Full pipeline: scrape social media → process → embed → store in vector DB.
    """
    try:
        print(f"\n{'='*60}")
        print(f"Starting pipeline for: {request.company_name}")
        print(f"{'='*60}\n")

        # Step 1: Resolve social media handles
        print("Step 1: Resolving social media handles...")
        handles = company_resolver.resolve(
            request.company_name,
            instagram=request.instagram_handle,
            linkedin=request.linkedin_url,
            twitter=request.twitter_handle
        )

        if not any(handles.values()):
            raise HTTPException(
                status_code=400,
                detail="No social media handles provided or found in database"
            )

        print(f"Resolved handles: {handles}\n")

        # Step 2: Scrape all platforms
        print("Step 2: Scraping social media platforms...")
        scraped_data = await ScrapingOrchestrator.scrape_all_platforms(
            instagram_handle=handles.get("instagram"),
            linkedin_url=handles.get("linkedin"),
            twitter_handle=handles.get("twitter")
        )

        if not scraped_data:
            raise HTTPException(status_code=500, detail="Failed to scrape any platform")

        # Log summary
        print("\nSCRAPED DATA SUMMARY:")
        for platform, data in scraped_data.items():
            if platform == "instagram":
                posts = data.get("last_10_posts_and_reels", [])
            elif platform == "linkedin":
                posts = data.get("recent_posts", [])
            elif platform == "twitter":
                posts = data.get("posts", [])
            else:
                posts = []
            print(f"  {platform}: {len(posts)} posts")

        # Step 3: Process and chunk
        print("\nStep 3: Processing and chunking text...")
        chunks = text_processor.process_all_platforms(scraped_data, request.company_name)

        if not chunks:
            raise HTTPException(status_code=500, detail="No valid content found to process")

        # Step 4: Store in vector DB
        print("\nStep 4: Generating embeddings and storing in vector DB...")
        vector_db.add_posts(request.company_name, chunks)

        # Step 5: Stats
        stats = vector_db.get_company_stats(request.company_name)

        print(f"\nPipeline complete for {request.company_name}!")

        return {
            "success": True,
            "company": request.company_name,
            "handles": handles,
            "platforms_scraped": list(scraped_data.keys()),
            "chunks_created": len(chunks),
            "total_posts_in_db": stats["total_posts"],
            "message": f"Successfully scraped and stored {len(chunks)} posts"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search_posts(request: SearchRequest):
    """
    Semantic search over stored posts for a company.
    """
    try:
        results = vector_db.search(
            company_name=request.company_name,
            query=request.query,
            top_k=request.top_k,
            platform_filter=request.platform_filter
        )

        return {
            "success": True,
            "company": request.company_name,
            "query": request.query,
            "results_count": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/company-stats/{company_name}")
async def get_company_stats(company_name: str):
    """Get statistics about stored data for a company."""
    try:
        stats = vector_db.get_company_stats(company_name)
        return {"success": True, **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/list-companies")
async def list_companies():
    """List all companies in the database."""
    try:
        companies = company_resolver.list_companies()
        return {
            "success": True,
            "companies": companies,
            "count": len(companies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/company/{company_name}")
async def delete_company(company_name: str):
    """Delete all stored data for a company."""
    try:
        vector_db.delete_company(company_name)
        return {
            "success": True,
            "message": f"Deleted all data for {company_name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
