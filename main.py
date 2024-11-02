from typing import Union, Optional
from enum import Enum
from docling.document_converter import DocumentConverter
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import HttpUrl, BaseModel
from io import BytesIO
from docling.datamodel.base_models import DocumentStream
from curl_cffi import requests
import os
from datetime import datetime
import shutil
from pathlib import Path
import asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.datamodel.pipeline_options import PdfPipelineOptions


# Add these constants at the top of the file with other imports
UPLOAD_DIR = Path("./document_queue")
PROCESSED_DIR = Path("./document_processed")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB in bytes
ALLOWED_EXTENSIONS = {
    '.pdf', '.docx', '.pptx', '.jpg', '.jpeg', '.png', '.html', 
    '.adoc', '.md', '.markdown'
}
UPLOAD_TIMEOUT = 120  # seconds

# Create directories if they don't exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    ALL = "all"

class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=UPLOAD_TIMEOUT)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=408,
                content={"error": f"Request timeout after {UPLOAD_TIMEOUT} seconds"}
            )

app = FastAPI()
app.add_middleware(TimeoutMiddleware)

@app.on_event("startup")
async def verify_models():
    """Verify that all required models are present"""
    try:
        # Verify PDF/Image models
        pipeline = StandardPdfPipeline(pipeline_options=PdfPipelineOptions())
        models_path = pipeline.artifacts_path
        
        # Check if critical model directories exist
        layout_path = models_path / StandardPdfPipeline._layout_model_path
        table_path = models_path / StandardPdfPipeline._table_model_path
        
        if not layout_path.exists() or not table_path.exists():
            raise RuntimeError("Required models are missing!")
            
    except Exception as e:
        print(f"Error verifying models: {e}")
        raise e

@app.post(
    "/convert",
    summary="Convert Document to Structured Format",
    description="""
    Convert a document (PDF, DOCX, PPTX, Images, HTML, AsciiDoc, Markdown) to a structured format.
    
    You can provide either:
    - The filepath to the document or
    - The URL to the document

    The output can be in either:
    - Markdown format (default)
    - JSON format
    
    The converter supports various document types and will attempt to preserve
    the document structure, including tables, lists, and formatting.
    """,
    response_description="Converted document content in the requested format"
)

async def convert_document(
    url: str = Query(..., description="URL or file path to the document to convert"),
    output_format: OutputFormat = Query(default=OutputFormat.MARKDOWN, description="Output format (markdown, json, all)")
) -> dict:
    """
    Convert a document to structured format (markdown or JSON).
    
    Args:
        url: URL or file path to the document
        output_format: Desired output format (markdown or json)
        
    Returns:
        dict: Contains the converted content under the 'content' key
    """
    converter = DocumentConverter()
    
    try:
        if not url.endswith(".html"):
            result = converter.convert(str(url))
        else:
            try:
                temp_file = False
                html_content = requests.get(url, impersonate="chrome")
                with open("tmp.html", "w", encoding='utf-8') as f:
                    f.write(html_content.text)
                    temp_file = True
                result = converter.convert("tmp.html")
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )
            finally:
                if temp_file:
                    os.remove("tmp.html")
            
        # Return based on requested format
        if output_format == OutputFormat.MARKDOWN:
            return {"markdown": result.document.export_to_markdown()}
        elif output_format == OutputFormat.JSON:
            return {"json": result.document.model_dump()}
        elif output_format == OutputFormat.ALL:
            return {"markdown": result.document.export_to_markdown(), "json": result.document.model_dump()}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
    
@app.post(
    "/upload-convert",
    summary="Convert Uploaded Document to Structured Format",
    description="""
    Convert an uploaded document (PDF, DOCX, PPTX, Images, HTML, AsciiDoc, Markdown) to a structured format.
    
    Maximum file size: 20MB
    Timeout: 120 seconds
    Supported formats: PDF, DOCX, PPTX, Images (JPG/PNG), HTML, AsciiDoc, Markdown
    
    Upload your document file directly and receive the converted output in either:
    - Markdown format (default)
    - JSON format
    - Both formats (all)
    
    The converter supports various document types and will attempt to preserve
    the document structure, including tables, lists, and formatting.
    """,
    response_description="Converted document content in the requested format"
)
async def upload_and_convert_document(
    file: UploadFile = File(...),
    output_format: OutputFormat = Query(default=OutputFormat.MARKDOWN, description="Output format (markdown, json, all)")
) -> dict:
    """
    Convert an uploaded document to structured format (markdown or JSON).
    
    Args:
        file: Uploaded document file
        output_format: Desired output format (markdown, json, or all)
        
    Returns:
        dict: Contains the converted content under the 'content' key
    """
    try:
        # Validate file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Check file size (read first chunk)
        first_chunk = await file.read(MAX_FILE_SIZE + 1)
        if len(first_chunk) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB"
            )
        
        # Reset file pointer
        await file.seek(0)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d")
        new_filename = f"{timestamp}_{file.filename}"
        queue_filepath = UPLOAD_DIR / new_filename
        processed_filepath = PROCESSED_DIR / new_filename

        # Save file to queue directory
        with open(queue_filepath, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
        
        try:
            # Use existing convert_document function with the queue filepath
            result = await convert_document(str(queue_filepath), output_format)
            
            # Move file to processed directory after successful conversion
            shutil.move(str(queue_filepath), str(processed_filepath))
            
            return result
            
        except Exception as e:
            # Clean up file from queue directory if conversion fails
            if queue_filepath.exists():
                queue_filepath.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Error processing document: {str(e)}"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )