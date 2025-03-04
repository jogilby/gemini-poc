import logging
import sys
import os
import json
from io import BytesIO
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import boto3
import google.cloud.documentai_v1 as documentai
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
import google.oauth2.service_account
from services.extraction_service import extract_and_chunk
from services.weaviate_service import create_collections, get_weaviate_client, insert_document_chunks
from services.ingestion_service import IngestionService
from database.dao.DocumentRecord import DocumentRecord


load_dotenv()

# Setup logging
def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # You can set different log levels for different modules
    logging.getLogger('services.weaviate_service').setLevel(logging.DEBUG)
    
    # Return the root logger if needed
    return logging.getLogger()

app = FastAPI()

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development, configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static directory to serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html from the root path
@app.get("/")
async def read_root():
    return FileResponse('static/index.html')


# Serve index.html from the root path
@app.get("/start")
async def read_root():
    return FileResponse('static/start.html')

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

# setup Google credentials for Document AI 
try:
        
    service_account_key_json_str = get_secretmanager_client().get_secret_value(SecretId=GOOGLE_SERVICE_ACCOUNT_SECRET_NAME)    
    if service_account_key_json_str:
        super_secret = service_account_key_json_str['SecretString']
        google_service_account_info = json.loads(str(super_secret))
    else:
        google_service_account_info = None
        print("Warning: google-service-account-key-prod secret not parsed. Falling back to default credentials.")
        # You might choose to raise an exception here in production if the key is mandatory
        # raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON_KEY environment variable not set.")
except Exception as e:
    print(f"Error loading Google Service Account key: {e}")
    # Handle error appropriately - maybe raise HTTPException or use default credentials if possible


def save_text_to_s3(s3_client, s3_bucket_name, pdf_key, text_content):
    """Saves extracted text content to S3 as a .txt file."""
    text_key = pdf_key.rsplit('.', 1)[0] + '.txt'  # Replace .pdf with .txt
    print(f"Saving extracted text to S3: {text_key}")
    try:
        s3_client.put_object(Bucket=s3_bucket_name, Key=text_key, Body=text_content.encode('utf-8'))
    except Exception as e:
        print(f"Error saving text to S3: {e}")

def load_text_from_s3(s3_client, s3_bucket_name, pdf_key):
    """Loads extracted text content from S3 if it exists."""
    text_key = pdf_key.rsplit('.', 1)[0] + '.txt'
    print(f"Checking for saved text in S3: {text_key}")
    try:
        response = s3_client.get_object(Bucket=s3_bucket_name, Key=text_key)
        return response['Body'].read().decode('utf-8')
    except s3_client.exceptions.NoSuchKey:
        print(f"No saved text found in S3 for: {text_key}")
        return None
    except Exception as e:
        print(f"Error loading text from S3: {e}")
        return None


def fetch_pdf_text_from_s3_document_ai(project_location):
    """
    Fetches text content from all PDF files within a specified folder in the S3 bucket,
    processes them page by page using Document AI, using saved text if available.

    Args:
        project_location (str): The folder path (prefix) in the S3 bucket to search within.
                                 If empty or None, it will search the entire bucket.
    Returns:
        str: Concatenated text content from all processed PDF files, separated by newlines.
    """
    s3_client = get_s3_client()
    pdf_texts = []
    try:
         # Instantiates a client
        if google_service_account_info: # Use service account credentials if available
            try:
                document_ai_client = documentai.DocumentProcessorServiceClient.from_service_account_info(google_service_account_info)
            except Exception as e:
                print(f"Error creating Document AI client with service account: {e}")
                raise HTTPException(status_code=500, detail=f"Error creating Document AI client with service account: {e}")
        else: # Fallback to default credentials (e.g., for local dev if ADC is configured)
            print("Using default Google Cloud credentials for Document AI client.")
            document_ai_client = documentai.DocumentProcessorServiceClient()
        # List objects in S3 bucket with the given prefix (project_location)
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=project_location)
        if 'Contents' in response:
            for obj in response['Contents']:
                pdf_key = obj['Key']
                if pdf_key.lower().endswith('.pdf'):                    
                    saved_text = load_text_from_s3(s3_client, S3_BUCKET_NAME, pdf_key)
                    if saved_text:
                        print(f"Using saved text from S3 for: {pdf_key}")
                        pdf_texts.append(saved_text)
                    else:
                        print(f"Extracting text from PDF page by page using Document AI: {pdf_key}", flush=True)
                        try:
                            pdf_file_bytes = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=pdf_key)['Body'].read()

                            pdf_reader = PdfReader(BytesIO(pdf_file_bytes))
                            page_count = len(pdf_reader.pages)
                            extracted_text_pages = []
                            for page_num in range(page_count):
                                page = pdf_reader.pages[page_num]
                                print(f"Extracting from {page_num} of {page_count} pages")
                                # Extract content of each page to bytes
                                with BytesIO() as page_bytes_stream:
                                    writer = PdfWriter()  # Create a NEW PdfWriter object here                                    
                                    writer.add_page(page)
                                    writer.write(page_bytes_stream)
                                    page_content_bytes = page_bytes_stream.getvalue()

                                page_text = process_pdf_with_document_ai(page_content_bytes, document_ai_client) # Process each page as PDF bytes
                                extracted_text_pages.append(page_text)

                            extracted_text = "\n".join(extracted_text_pages) # Join text from all pages
                            pdf_texts.append(extracted_text)
                            save_text_to_s3(s3_client, S3_BUCKET_NAME, pdf_key, extracted_text) # Save text to S3
                        except Exception as e:
                            print(f"Error processing {pdf_key} with Document AI page by page: {e}")
                else:
                    print(f"Skipping non-PDF file: {pdf_key}") # Added logging for non-PDF files
        else:
            print(f"No files found in S3 bucket under location: {project_location} in bucket: {S3_BUCKET_NAME}")
    except Exception as e:
        print(f"Error accessing S3 bucket: {e}")
    return "\n".join(pdf_texts)

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
        raise HTTPException(status_code=500, detail=f"Error processing PDF with Document AI: {e}")


def call_gemini_api(query, context_text):
    """Calls the Gemini API with the given query and context."""
    prompt_parts = [
        {"text": f"Context information from PDF documents:\n\n{context_text}\n\nUser Query: {query}\n\nAnswer the user query based on the provided context. If the context is not relevant, answer to the best of your ability."}
    ]
    try:
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        return f"Error calling Gemini API: {e}"

@app.post("/query")
async def ask_gemini_with_context(request: Request):
    """API endpoint to handle user queries and interact with Gemini."""
    try:
        data = await request.json()
        user_query = data.get('query')
        project_location = data.get('location') # Expecting 'location' from the request body for project location
        print(f"Received user query: {user_query} about project {project_location}", flush=True)

        if not user_query:
            raise HTTPException(status_code=400, detail="No query provided")

        pdf_context = fetch_pdf_text_from_s3_document_ai(project_location) # Pass project_location to the function
        gemini_response = call_gemini_api(user_query, pdf_context)

        return JSONResponse({"response": gemini_response})

    except HTTPException as http_exc:
        return http_exc
    except Exception as e:
        print(f"Error processing user query: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


if __name__ == "__main__":
    configure_logging()
    # Initialize Weaviate collections on first run

    client = get_weaviate_client()
    create_collections(client, recreate_if_exists=False)
    print("Weaviate collections initialized successfully.")
        
    from database.dbutil import Database  # Adjust the import according to your actual database module
    from database.dao.DocumentDAO import DocumentDAO
    from database.dao.UserDAO import UserDAO
    from database.dao.ProjectDAO import ProjectDAO
    from services.weaviate_service import get_weaviate_client
    
    file_path = 'files/1-G0.5ArchSpecs.pdf'
    with open(file_path, 'rb') as file:
        file_bytes = file.read()    

    with ProjectDAO() as prj, DocumentDAO() as doc:      
        dr = doc.get_document(20)        
        with IngestionService(get_weaviate_client()) as ingest:
            ingest.ingest_document(dr, file_bytes, True)


    """
    # Read bytes from a file into a buffer
    file_path = 'files/1-G0.5ArchSpecs.pdf'
    with open(file_path, 'rb') as file:
        file_bytes = file.read()    
    chunk_list = extract_and_chunk(file_bytes, 0)
    print(f"Extracted {len(chunk_list)} from pdf")
    weaviate_client = get_weaviate_client()
    document = DocumentRecord("1", "G0.5ArchSpecs.pdf", 1, "https://example.com", 1)
    insert_document_chunks(weaviate_client, document, chunk_list)
    print("Inserted document chunks")
    """
    #import uvicorn
    #uvicorn.run(app, host="0.0.0.0", port=8000, debug=True, reload=True)