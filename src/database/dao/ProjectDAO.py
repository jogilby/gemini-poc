from database.dbutil import Database

class ProjectDAO:
    def __init__(self):
        self.db = Database()

    def __enter__(self):
        if self.db:
            self.db.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db: self.db.close()        
        
    def get_project(self, document_id):
        """Get a project by its ID"""
        query = """
            SELECT * FROM projects 
            WHERE id = %s
        """
        params = (document_id,)
        return self.db.execute_query(query, params, fetch=True)
    
    def create_project(self, name, organization_id, created_by_user):
        """Create a new project"""
        query = """
            INSERT INTO projects (name, organization_id, created_by_user)
            VALUES (%s, %s, %s)
            RETURNING *
        """
        params = (name, organization_id, created_by_user)
        return self.db.execute_query(query, params, fetch=True)
    
    def update_project(self, project_id, name = None, organization_id = None):
        """Update an existing project"""
        # Build dynamic query based on provided parameters
        set_clauses = []
        params = []
        
        if name is not None:
            set_clauses.append("name = %s")
            params.append(name)
        
        if organization_id is not None:
            set_clauses.append("organization_id = %s")
            params.append(organization_id)
            
        if not set_clauses:
            return None  # Nothing to update
            
        set_clause = ", ".join(set_clauses)
        params.append(project_id)  # For the WHERE clause
        
        query = f"""
            UPDATE projects
            SET {set_clause}
            WHERE id = %s
            RETURNING *
        """
        
        return self.db.execute_query(query, params, fetch=True)
    
    def delete_project(self, project_id):
        """Delete a project"""
        query = """
            DELETE FROM projects
            WHERE id = %s
            RETURNING id
        """
        params = (project_id,)
        return self.db.execute_query(query, params, fetch=True)
    
    def get_projects_by_organization(self, organization_id):
        """Get all projects for an organization"""
        query = """
            SELECT * FROM projects
            WHERE organization_id = %s
            ORDER BY created_at DESC
        """
        params = (organization_id,)
        return self.db.execute_query(query, params, fetch=True)