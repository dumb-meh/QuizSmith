import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.services.single_book_suggestion.single_book_suggestion_route import router as single_book_suggestion_router
from app.services.regenerate_plan.regenerate_plan_route import router as regenerate_plan_router


app = FastAPI(
    title="Vuku AI",
    description="AI service for Quiz generation and management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(single_book_suggestion_router, tags=["Single Book"])
app.include_router(regenerate_plan_router, tags=["Regenerate Plan"])


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health checks"""
    return {
        "message": "Welcome to the Vuku AI!",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Docker/monitoring"""
    return {
        "status": "healthy",
        "service": "Vuku AI"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=9093, 
        reload=True
    )