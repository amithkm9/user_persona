from mistralai import Mistral #type:ignore

def extract_cv_to_markdown(document_url: str, api_key: str = "KkDJpOtCRYJjq514rwKUjJlxPN9idCSN") -> str:
    """
    Extracts text from a PDF document using Mistral OCR and returns it as a markdown string.

    Args:
        document_url (str): The URL of the document to be processed.
        api_key (str): API key for Mistral. Default is the provided key.
        
    Returns:
        str: The extracted markdown content from the document.
    """
    client = Mistral(api_key=api_key)
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