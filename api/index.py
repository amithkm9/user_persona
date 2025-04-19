# api/index.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os
import traceback

# Add parent directory to path so we can import our app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our main app
try:
    from main import app as main_app
except Exception as e:
    print(f"Error importing main app: {str(e)}")
    traceback.print_exc()
    # Create a dummy app if import fails
    main_app = FastAPI()
    
    @main_app.get("/generate_persona")
    def error_endpoint():
        return {"error": f"Failed to load main application: {str(e)}"}

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handling middleware
@app.middleware("http")
async def errors_handling(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        error_detail = str(exc)
        return JSONResponse(
            status_code=500,
            content={"detail": error_detail, "traceback": traceback.format_exc()}
        )

# Mount our main app
app.mount("/api", main_app)

# Root endpoint for a simple health check or landing page
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>CV Persona Builder API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1 {
                    color: #333;
                }
                code {
                    background-color: #f4f4f4;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
            </style>
        </head>
        <body>
            <h1>CV Persona Builder API</h1>
            <p>The API is running. Use the <code>/api/generate_persona</code> endpoint to generate personas.</p>
        </body>
    </html>
    """

@app.get("/debug")
async def debug():
    """Debug endpoint to check if environment variables are properly set"""
    env_vars = {
        "MISTRAL_API_KEY": os.environ.get("MISTRAL_API_KEY", "").startswith("..."),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "").startswith("..."),
        "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", "").startswith("..."),
        "NEO4J_URI": os.environ.get("NEO4J_URI", "Not set"),
        "NEO4J_USERNAME": os.environ.get("NEO4J_USERNAME", "Not set"),
        "NEO4J_PASSWORD": bool(os.environ.get("NEO4J_PASSWORD")),
        "PYTHON_VERSION": sys.version,
        "IMPORT_PATHS": sys.path
    }
    return {"env_vars": env_vars}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

