from database.dbutil import Database
from database.dao.DocumentRecord import DocumentRecord

class DocumentDAO:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        if self.db:
            self.db.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db: self.db.close()        
        
    def get_document(self, document_id):
        """Get a document by its ID"""
        query = """
            SELECT id, file_name, project_id, source_url, source_page FROM documents 
            WHERE id = %s
        """
        params = (document_id,)
        record = self.db.execute_query(query, params, fetch=True)
        if not record: 
            return None
        return DocumentRecord(record[0][0], record[0][1], record[0][2], record[0][3], record[0][4])
    
    def create_document(self, document_record: DocumentRecord):
        """Create a new document"""
        query = """
            INSERT INTO documents (project_id, file_name, source_url, source_page)
            VALUES (%s, %s, %s, %s)
            RETURNING id, file_name, project_id, source_url, source_page
        """
        params = (document_record.project_id, document_record.file_name, document_record.source_url, document_record.source_page)
        result = self.db.execute_query(query, params, fetch=True)[0]
        return DocumentRecord(result[0], result[1], result[2], result[3], result[4])
    
    def update_document(self, document_record: DocumentRecord):
        """Update an existing document"""
        # Build dynamic query based on provided parameters
        set_clauses = []
        params = []
        
        if document_record.file_name is not None:
            set_clauses.append("file_name = %s")
            params.append(document_record.file_name)
        
        if document_record.source_url is not None:
            set_clauses.append("source_url = %s")
            params.append(document_record.source_url)
            
        if document_record.source_page is not None:
            set_clauses.append("source_page = %s")
            params.append(document_record.source_page)
            
        if not set_clauses:
            return None  # Nothing to update
            
        set_clause = ", ".join(set_clauses)
        params.append(document_record.document_id)  # For the WHERE clause
        
        query = f"""
            UPDATE documents
            SET {set_clause}
            WHERE id = %s
            RETURNING id, file_name, project_id, source_url, source_page
        """
        record = self.db.execute_query(query, params, fetch=True)
        if not record: 
            return None
        return DocumentRecord(record[0][0], record[0][1], record[0][2], record[0][3], record[0][4])
            
    
    def delete_document(self, document_id):
        """Delete a document"""
        query = """
            DELETE FROM documents
            WHERE id = %s
            RETURNING id
        """
        params = (document_id,)
        return self.db.execute_query(query, params, fetch=True)
    
    def get_documents_by_project(self, project_id):
        """Get all documents for a project"""
        query = """
            SELECT * FROM documents
            WHERE project_id = %s
            ORDER BY created_at DESC
        """
        params = (project_id,)
        return self.db.execute_query(query, params, fetch=True)