import pytest
from unittest.mock import MagicMock, patch
import logging

from services.ingestion_service import IngestionService
from database.dao.DocumentDAO import DocumentDAO
from database.dao.DocumentRecord import DocumentRecord


class TestIngestionService:
    @pytest.fixture
    def mock_weaviate_client(self):
        return MagicMock()
        
    @pytest.fixture
    def mock_document_dao(self):
        mock_dao = MagicMock(spec=DocumentDAO)
        return mock_dao
        
    @pytest.fixture
    def mock_logger(self):
        return MagicMock(spec=logging.Logger)
        
    @pytest.fixture
    def mock_extraction_service(self):
        mock_service = MagicMock()
        mock_service.extract_and_chunk = MagicMock(return_value=[
            {"text": "Test chunk 1", "metadata": {"page": 1}},
            {"text": "Test chunk 2", "metadata": {"page": 2}}
        ])
        return mock_service
        
    @pytest.fixture
    def mock_weaviate_service(self):
        mock_service = MagicMock()
        mock_service.insert_document_chunks = MagicMock()
        mock_service.remove_document_chunks = MagicMock()
        return mock_service
        
    @pytest.fixture
    def sample_document_record(self):
        return DocumentRecord(
            document_id=None,
            file_name="test_document.pdf",
            project_id=10,
            source_url="http://test.com",
            source_page=1
        )
    
    @pytest.fixture
    def ingestion_service(self, mock_weaviate_client, mock_document_dao, mock_logger, 
                        mock_extraction_service, mock_weaviate_service):
        return IngestionService(
            weaviate_client=mock_weaviate_client,
            document_dao=mock_document_dao,
            logger=mock_logger,
            extraction_service_module=mock_extraction_service,
            weaviate_service_module=mock_weaviate_service
        )
    
    def test_init(self, mock_weaviate_client, mock_document_dao):
        """Test that IngestionService initializes correctly with default values"""
        service = IngestionService(mock_weaviate_client, mock_document_dao)
        assert service.weaviate_client == mock_weaviate_client
        assert service.document_dao is not None
        assert service.logger is not None
    
    def test_context_manager(self, ingestion_service):
        """Test that IngestionService works as a context manager"""
        with ingestion_service as service:
            assert service is ingestion_service
    
    def test_ingest_document_success(self, ingestion_service, sample_document_record, mock_document_dao):
        """Test successful document ingestion"""
        # Setup
        document_bytes = b"test document content"
        mock_document_dao.create_document.return_value = DocumentRecord(
            document_id=123,
            file_name="test_document.pdf",
            project_id=10,
            source_page=0,
            source_url="http://test.com"
        )    
        
        # Execute
        result = ingestion_service.ingest_document(sample_document_record, document_bytes)
        
        # Assert
        assert result == 123
        mock_document_dao.create_document.assert_called_once_with(sample_document_record)
        ingestion_service.extraction_service.extract_and_chunk.assert_called_once_with(document_bytes, 0)
        ingestion_service.weaviate_service.insert_document_chunks.assert_called_once()
        ingestion_service.logger.info.assert_called()
    
    def test_ingest_document_reingest(self, ingestion_service, mock_document_dao, mock_weaviate_service):
        """Test document re-ingestion"""
        # Setup
        document_bytes = b"test document content"
        doc_record = DocumentRecord(
            document_id=456,
            file_name="test_document.pdf",
            project_id=10,
            source_page=0,
            source_url="http://test.com"
        )
        mock_document_dao.update_document.return_value = doc_record
        
        # Execute
        result = ingestion_service.ingest_document(doc_record, document_bytes, allow_reingest=True)
        
        # Assert
        assert result == 456
        mock_document_dao.update_document.assert_called_once_with(doc_record)
        mock_weaviate_service.remove_document_chunks.assert_called_once_with(
            ingestion_service.weaviate_client, 456
        )
        ingestion_service.extraction_service.extract_and_chunk.assert_called_once_with(document_bytes, 0)
    
    def test_ingest_document_reingest_without_permission(self, ingestion_service, sample_document_record):
        """Test that re-ingestion fails when not allowed"""
        # Setup
        document_bytes = b"test document content"
        doc_record = DocumentRecord(
            document_id=789,
            file_name="test_document.pdf",
            project_id=10,
            source_page=0,
            source_url="http://test.com"
        )
        
        # Execute & Assert
        with pytest.raises(ValueError, match="document_id only allowed when re-ingesting document"):
            ingestion_service.ingest_document(doc_record, document_bytes, allow_reingest=False)
    
    def test_ingest_document_no_chunks(self, ingestion_service, sample_document_record, mock_document_dao, 
                                    mock_extraction_service):
        """Test document ingestion when no chunks are extracted"""
        # Setup
        document_bytes = b"test document content"
        mock_document_dao.create_document.return_value = DocumentRecord(
            document_id=111,
            file_name="test_document.pdf",
            project_id=10,
            source_page=0,
            source_url="http://test.com"
        )
        # Mock extraction service to return no chunks
        mock_extraction_service.extract_and_chunk.return_value = []
        
        # Execute
        result = ingestion_service.ingest_document(sample_document_record, document_bytes)
        
        # Assert
        assert result == 111
        ingestion_service.weaviate_service.insert_document_chunks.assert_not_called()
        ingestion_service.logger.warning.assert_called()
    
    def test_ingest_document_db_failure(self, ingestion_service, sample_document_record, mock_document_dao):
        """Test document ingestion when database creation fails"""
        # Setup
        document_bytes = b"test document content"
        mock_document_dao.create_document.return_value = DocumentRecord(
            document_id=None,  # Simulate DB failure - no ID returned
            file_name="test_document.pdf",
            project_id=10,
            source_page=0,
            source_url="http://test.com"
        )
        
        # Execute
        result = ingestion_service.ingest_document(sample_document_record, document_bytes)
        
        # Assert
        assert result is None
        ingestion_service.logger.error.assert_called()
        ingestion_service.extraction_service.extract_and_chunk.assert_not_called()
    
    def test_ingest_document_exception(self, ingestion_service, sample_document_record, mock_extraction_service):
        """Test document ingestion when an exception occurs"""
        # Setup
        document_bytes = b"test document content"
        mock_extraction_service.extract_and_chunk.side_effect = Exception("Test exception")
        
        # Execute
        result = ingestion_service.ingest_document(sample_document_record, document_bytes)
        
        # Assert
        assert result is None
        ingestion_service.logger.error.assert_called()
