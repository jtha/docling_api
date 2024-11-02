from docling.document_converter import DocumentConverter, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from pathlib import Path

def download_models():
    """
    Initialize all pipelines to trigger model downloads
    """
    print("Starting model downloads...")
    
    # First, download PDF/Image models (these are the heavy ones)
    print("Downloading PDF/Image processing models...")
    pdf_pipeline = StandardPdfPipeline(pipeline_options=PdfPipelineOptions())
    
    # Force model downloads by accessing the models directory
    models_path = pdf_pipeline.artifacts_path
    print(f"Models downloaded to: {models_path}")
    
    # Initialize converter with all formats to ensure other format handlers are ready
    print("Initializing all document format handlers...")
    converter = DocumentConverter()
    
    # Initialize pipelines for all formats
    for format in InputFormat:
        print(f"Initializing pipeline for {format}...")
        converter.initialize_pipeline(format)
    
    print("All models and format handlers are initialized!")

if __name__ == "__main__":
    download_models()