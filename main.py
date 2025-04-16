from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
import json
from typing import List
from agent import KGAgent

# Set fixed API key
API_KEY = "AIzaSyAwjHgfipkRfZfmrTl-tDsY-7UfAKjcTu8"

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph Agent API",
    description="API for querying information using a Knowledge Graph Agent",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"]
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Define request models
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    result: str

# Root endpoint serving the HTML interface
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API endpoint for queries
@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    try:
        # Initialize the agent with the fixed API key
        agent = KGAgent(api_key=API_KEY)
        async def stream_response():
            for chunk in agent.QAgent(query=request.query):
                # Yield each chunk as a Server-Sent Event (SSE)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            # End of stream
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  
            }
        )
        # # Execute the query
        # result = agent.QAgent(query=request.query)
        # print(f"Result type: {type(result)}")  # Check the type
        # print(f"Result length: {len(result) if result else 0}")
        
        # # Return the result
        # return QueryResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Run the API with uvicorn if script is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)