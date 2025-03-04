import boto3
from io import BytesIO
import json
import os
from pypdf import PdfReader, PdfWriter
import google.cloud.documentai_v1 as documentai
import google.generativeai as genai

""" This service is responsible for extracting content from PDF files and preparing
it for storage in Weaviate. """


# Configure AWS, Gemini API and Google Cloud Document AI credentials
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Google Cloud Document AI Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
PROCESSOR_ID = os.getenv("GOOGLE_DOCUMENT_AI_PROCESSOR_ID")
PROCESSOR_LOCATION = os.getenv("GOOGLE_DOCUMENT_AI_PROCESSOR_LOCATION")
GOOGLE_SERVICE_ACCOUNT_SECRET_NAME = os.getenv("GOOGLE_SERVICE_ACCOUNT_SECRET_NAME")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

def get_s3_client():
    """Creates and returns an S3 client."""
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION_NAME
    )
def get_secretmanager_client():
    """Creates and returns a secretmanager client."""
    return boto3.client(
        'secretsmanager',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION_NAME
    )
def get_documentai_client():
    """Creates and returns a Document AI client."""
     # Instantiates a client
    if google_service_account_info: # Use service account credentials if available
        try:
            client = documentai.DocumentProcessorServiceClient.from_service_account_info(google_service_account_info)
        except Exception as e:
            print(f"Error creating Document AI client with service account: {e}")
            raise e
    else: # Fallback to default credentials (e.g., for local dev if ADC is configured)
        print("Using default Google Cloud credentials for Document AI client.")
        client = documentai.DocumentProcessorServiceClient()
    return client

# setup Google credentials for Document AI 
try:
        
    service_account_key_json_str = get_secretmanager_client().get_secret_value(SecretId=GOOGLE_SERVICE_ACCOUNT_SECRET_NAME)    
    if service_account_key_json_str:
        super_secret = service_account_key_json_str['SecretString']
        google_service_account_info = json.loads(str(super_secret))
    else:
        google_service_account_info = None
        print("Warning: google-service-account-key-prod secret not parsed. Falling back to default credentials.")
except Exception as e:
    print(f"Error loading Google Service Account key: {e}")
    print("Exception loading google service account, will try default credentials")


def extract_and_chunk(pdf_file_bytes, chunk_len=0, use_document_ai=False) -> list:
    """
        Extracts content from a PDF file and returns a list of chunks.
        pdf_file_bytes: Bytes of the PDF file to process
        chunk_len: Maximum length of each chunk (0 for one chunk per page)
    """
    try:
        if chunk_len != 0:
            raise NotImplementedError("Chunking is not implemented yet.")
        if use_document_ai:
            document_ai_client = get_documentai_client()
        else:
            document_ai_client = None
        chunk_list = []
        pdf_texts = []
        pdf_reader = PdfReader(BytesIO(pdf_file_bytes))
        page_count = len(pdf_reader.pages)
        extracted_text_pages = []
        for page_num in range(page_count):
            page = pdf_reader.pages[page_num]
            if document_ai_client:
                print(f"Extracting from {page_num} of {page_count} pages with Document AI.")
                # Extract content of each page to bytes
                with BytesIO() as page_bytes_stream:
                    writer = PdfWriter()  # Create a NEW PdfWriter object here                                    
                    writer.add_page(page)
                    writer.write(page_bytes_stream)
                    page_content_bytes = page_bytes_stream.getvalue()
                    page_text = process_pdf_with_document_ai(page_content_bytes, document_ai_client) # Process each page as PDF bytes
            else:
                print(f"Extracting from {page_num} of {page_count} pages with pypdf.")
                page_text = page.extract_text() # use Pypdf temporarily            
            # SAVE TO CHUNKS LIST HERE
            chunk_list.append(page_text)
            #extracted_text_pages.append(page_text)

        #extracted_text = "\n".join(extracted_text_pages) # Join text from all pages
        #pdf_texts.append(extracted_text)
        #save_text_to_s3(s3_client, S3_BUCKET_NAME, pdf_key, extracted_text) # Save text to S3
    except Exception as e:
        raise e
        #print(f"Error processing {pdf_key} with Document AI page by page: {e}")
          
    return chunk_list


def process_pdf_with_document_ai(file_content: bytes, document_ai_client) -> str:
    """Processes a single PDF file content (or a page) using Google Document AI and returns extracted text."""
   
    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processors/processor-id
    name = document_ai_client.processor_path(
        PROJECT_ID, PROCESSOR_LOCATION, PROCESSOR_ID
    )
    # Load binary document from file path
    raw_document_object = documentai.RawDocument(content=file_content, mime_type="application/pdf") # Create RawDocument object
    # Configure the process request
    request = documentai.ProcessRequest(name=name, raw_document=raw_document_object) # Use raw_document parameter
    try:
        # Recognizes text in the PDF document
        result = document_ai_client.process_document(request=request)
        document_object = result.document
        document_text = document_object.text
        document_pages = document_object.pages
        for page in document_pages:
            if page.tables:
                print(f"Page {page.page_number} has {len(page.tables)} tables.")
        return document_text
    except Exception as e:
        print(f"Error processing PDF with Document AI: {e}")
        raise e

