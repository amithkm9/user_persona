from mistralai import Mistral #type:ignore
from config import MISTRAL_API_KEY

def extract_cv_to_markdown(document_url: str, api_key: str = None) -> str:
    """
    Extracts text from a PDF document using Mistral OCR and returns it as a markdown string.

    Args:
        document_url (str): The URL of the document to be processed.
        api_key (str, optional): API key for Mistral. If not provided, uses the environment variable.
        
    Returns:
        str: The extracted markdown content from the document.
    """
    # Use provided API key or fallback to environment variable
    mistral_api_key = api_key or MISTRAL_API_KEY
    
    if not mistral_api_key:
        raise ValueError("Mistral API key not provided and not found in environment variables")
    
    client = Mistral(api_key=mistral_api_key)
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": document_url
        },
        include_image_base64=True
    )

    # Combine all markdown pages into a single string
    markdown_content = ""
    for page in ocr_response.pages:
        markdown_content += page.markdown + "\n\n"
    
    return markdown_content