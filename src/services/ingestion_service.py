import logging
from database.dao.DocumentDAO import DocumentDAO
from services import extraction_service
from services import weaviate_service
from database.dao import DocumentRecord

class IngestionService:
    def __init__(self, weaviate_client, document_dao, extraction_service_module=None, weaviate_service_module=None, logger=None):
        """
        Initialize the ingestion service with dependencies
        
        Args:
            weaviate_client: Initialized Weaviate client
            document_dao: DocumentDAO instance for database operations
            logger: Logger instance (will create one if not provided)
            extraction_service_module: Module for extraction services (for testing)
            weaviate_service_module: Module for weaviate services (for testing)
        """
        self.document_dao = document_dao
        self.weaviate_client = weaviate_client
        self.logger = logger if logger is not None else logging.getLogger(__name__)
        self.extraction_service = extraction_service_module or extraction_service
        self.weaviate_service = weaviate_service_module or weaviate_service

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        return      

    def ingest_document(self, document_record: DocumentRecord, document_bytes, allow_reingest = False):
        """
        Process a document through the full ingestion pipeline:
        1. Store document metadata in PostgreSQL
        2. Extract content into chunks
        3. Store chunks in Weaviate vector database
        
        Args:
            document_record: DocumentRecord object containing document metadata
            document_bytes: Raw bytes of the document file
            
        Returns:
            Document ID if successful, None if failed
        """
        
        if allow_reingest and document_record.document_id:
            # Remove existing document and chunks
            self.logger.info(f"Re-ingesting document: {document_record.document_id}")
            self.weaviate_service.remove_document_chunks(self.weaviate_client, document_record.document_id)
            document_record = self.document_dao.update_document(document_record)
        else:
            if document_record.document_id:
                raise ValueError("document_id only allowed when re-ingesting document")
            # Create document in PostgreSQL database
            self.logger.info(f"Creating document record in database: {document_record.file_name}")
            document_record = self.document_dao.create_document(document_record)
            if not document_record.document_id:
                self.logger.error("Failed to create document record in database")
                return None
        document_id = document_record.document_id
        try:
            # Step 2: Extract content into chunks
            self.logger.info(f"Extracting content from document: {document_id}")
            chunks = self.extraction_service.extract_and_chunk(document_bytes, 0)

            if not chunks:
                self.logger.warning(f"No content chunks extracted from document: {document_id}")
                return document_id
            
            # Step 3: Store chunks in Weaviate            
            self.logger.info(f"Storing {len(chunks)} chunks in Weaviate for document: {document_id}")
              
            # Store chunk in Weaviate
            self.weaviate_service.insert_document_chunks(self.weaviate_client, document_record, chunks)
            
            self.logger.info(f"Document ingestion completed successfully: {document_id}")
            return document_id
            
        except Exception as e:
            self.logger.error(f"Error ingesting document: {e}")
            return None

