from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import boto3
import google.cloud.documentai_v1 as documentai
import google.generativeai as genai
import os
from dotenv import load_dotenv
from io import BytesIO
from pypdf import PdfReader, PdfWriter

load_dotenv()

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
        # List objects in S3 bucket with the given prefix (project_location)
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=project_location)
        if 'Contents' in response:
            for obj in response['Contents']:
                pdf_key = obj['Key']
                if pdf_key.lower().endswith('.pdf'):
                    print(f"Processing PDF: {pdf_key}")
                    saved_text = load_text_from_s3(s3_client, S3_BUCKET_NAME, pdf_key)
                    if saved_text:
                        print(f"Using saved text from S3 for: {pdf_key}")
                        pdf_texts.append(saved_text)
                    else:
                        print(f"Extracting text from PDF page by page using Document AI: {pdf_key}")
                        try:
                            pdf_file_bytes = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=pdf_key)['Body'].read()

                            pdf_reader = PdfReader(BytesIO(pdf_file_bytes))
                            extracted_text_pages = []
                            for page_num in range(len(pdf_reader.pages)):
                                page = pdf_reader.pages[page_num]
                                # Extract content of each page to bytes
                                with BytesIO() as page_bytes_stream:
                                    writer = PdfWriter()  # Create a NEW PdfWriter object here                                    
                                    writer.add_page(page)
                                    writer.write(page_bytes_stream)
                                    page_content_bytes = page_bytes_stream.getvalue()

                                page_text = process_pdf_with_document_ai(page_content_bytes) # Process each page as PDF bytes
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

def process_pdf_with_document_ai(file_content: bytes) -> str:
    """Processes a single PDF file content (or a page) using Google Document AI and returns extracted text."""
    # Instantiates a client
    document_ai_client = documentai.DocumentProcessorServiceClient()
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

        if not user_query:
            raise HTTPException(status_code=400, detail="No query provided")

        pdf_context = fetch_pdf_text_from_s3_document_ai(project_location) # Pass project_location to the function
        gemini_response = call_gemini_api(user_query, pdf_context)

        return JSONResponse({"response": gemini_response})

    except HTTPException as http_exc:
        return http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, debug=True, reload=True)