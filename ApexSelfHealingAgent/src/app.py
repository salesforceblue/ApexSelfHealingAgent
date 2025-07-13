"""FastAPI app exposing the exception-fix endpoint."""
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .orchestrator import process_exception

class ExceptionRequest(BaseModel):
    exception_id: str
    exception_message: str
    stack_trace: str

class ExceptionResponse(BaseModel):
    status: str
    message: str
    exception_id: str
    pr_url: str = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.post('/solve', response_model=ExceptionResponse)
def solve_exception(req: ExceptionRequest):
    """
    Accept exception request from Salesforce and process synchronously.
    Returns the result after processing is complete.
    """
    try:
        print(f"📨 Received exception request {req.exception_id}, processing synchronously")
        
        # Process the exception synchronously
        pr_url = process_exception(req.exception_id, req.exception_message, req.stack_trace)
        
        print(f"✅ Successfully processed exception {req.exception_id}: {pr_url}")
        
        # Return success response with PR URL
        return ExceptionResponse(
            status="success",
            message="Exception processed successfully",
            exception_id=req.exception_id,
            pr_url=pr_url
        )
        
    except Exception as e:
        print(f"❌ Failed to process exception {req.exception_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process exception: {str(e)}")

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
