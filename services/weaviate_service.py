import argparse
import weaviate
import os
from dotenv import load_dotenv
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter
from weaviate.classes.config import Configure, Property, DataType
from services.DocumentRecord import DocumentRecord

""" This service is responsible for connecting to Weaviate and managing the data in the Document collection."""

# Get Weaviate URL and API key from environment variables
WEAVIATE_URL = os.getenv("WEAVIATE_REST_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

def get_weaviate_client():
    """
    Connect to Weaviate and return the client object.
    """
    print(f"Connecting to Weaviate", WEAVIATE_URL)
    # Connect to Weaviate with authentication if API key is provided
    if WEAVIATE_API_KEY:   
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=WEAVIATE_URL,                                   
            auth_credentials=Auth.api_key(WEAVIATE_API_KEY)            
        )        
    else:
        raise ValueError("API key is required to connect to Weaviate")
    
    return client

def create_collections(client, recreate_if_exists=False):
    """
    Create collections in Weaviate.
    """    
    collection_name = "Document"
    if client.collections.exists(collection_name):
        if recreate_if_exists:
            client.collections.delete(collection_name)  # THIS WILL DELETE ALL DATA IN THE COLLECTION
        else:
            return; # Collection already exists, not recreating

    # Create the collection    
    client.collections.create(collection_name, 
                            properties=[Property(name="project_id", data_type=DataType.INT),
                                        Property(name="file_id", data_type=DataType.TEXT),
                                        Property(name="file_name", data_type=DataType.TEXT),
                                        Property(name="source_url", data_type=DataType.TEXT),
                                        Property(name="source_page", data_type=DataType.INT),
                                        Property(name="chunk_no", data_type=DataType.TEXT),                                        
                                        Property(name="contents", data_type=DataType.TEXT)
                            ],
                            vectorizer_config=[Configure.NamedVectors.text2vec_weaviate(
                                name="chunk_vector",
                                source_properties=["file_name", "contents"],
                                model="Snowflake/snowflake-arctic-embed-l-v2.0"
                            )]
    )
    return
    

def insert_document_chunks(client, document: DocumentRecord, chunks):
    """
    Connect to Weaviate and insert records for file content chunks. This will always insert and
    does not check for existence.
    
    Args:
        chunks: A list of dictionaries, each containing the chunk data with keys 'project_id', 'file_id', 
                'file_name', 'source_location', 'source_page', and 'chunk_content'.
    """
        
    # Check if the records already exist using the file_id
    documents = client.collections.get("Document")

    
    """ query_result = documents.query.fetch_objects(
        filters=(Filter.by_property("file_id").equal(chunk["file_id"])
                ),
        limit = 1
    )    
    print(f"returned", len(query_result.objects))"""
        
    # Insert the records
    with documents.batch.dynamic() as batch:
        for chunk in chunks:
            batch.add_object({"file_id": document.file_id, 
                                "file_name": document.file_name, 
                                "project_id": document.project_id,
                                "source_url": document.source_url,
                                "source_page": document.source_page,
                                "contents": chunk})
            if batch.number_errors > 10:
                print("Batch import stopped due to excessive errors.")
                break

        failed_objects = documents.batch.failed_objects
        if failed_objects:
            print(f"Number of failed imports: {len(failed_objects)}")
            print(f"First failed object: {failed_objects[0]}")
        else:    
            print(f"Inserting record with file_id: {document.file_id}")
    
    return True

def remove_document(client, file_id):
    """
    Remove a document from Weaviate.
    """
    documents = client.collections.get("Document")
    documents.data.delete_many(
        where=Filter.by_property("file_id").equal(file_id)
    )
    return
    