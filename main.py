from typing import Union, Optional
from enum import Enum
from docling.document_converter import DocumentConverter
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pydantic import HttpUrl, BaseModel
from io import BytesIO
from docling.datamodel.base_models import DocumentStream
from curl_cffi import requests
import os

class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

app = FastAPI()

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
    output_format: OutputFormat = Query(default=OutputFormat.MARKDOWN, description="Output format (markdown or json)")
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
        if url.endswith(".html"):
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
            return {"content": result.document.export_to_markdown()}
        else:  # JSON
            return {"content": result.document.model_dump()}
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )