from database.dbutil import Database

class OrganizationDAO:
    def __init__(self):
        self.db = Database()

    def __enter__(self):
        if self.db:
            self.db.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db: self.db.close()        
        
    def get_organization(self, organization_id):
        """Get an organization by its ID"""
        query = """
            SELECT * FROM organizations 
            WHERE id = %s;
        """
        params = (organization_id,)
        return self.db.execute_query(query, params, fetch=True)
    
    def create_organization(self, name):
        """Create a new organization"""
        query = """
            INSERT INTO organizations (name)
            VALUES (%s)
            RETURNING *;
        """
        params = (name,)
        return self.db.execute_query(query, params, fetch=True, close_after=False)
    
    def update_organization(self, organization_id, name = None):
        """Update an existing organization"""
        # Build dynamic query based on provided parameters
        set_clauses = []
        params = []
        
        if name is not None:
            set_clauses.append("name = %s")
            params.append(name)
        
        if not set_clauses:
            return None  # Nothing to update
            
        set_clause = ", ".join(set_clauses)
        params.append(organization_id)  # For the WHERE clause
        
        query = f"""
            UPDATE organizations
            SET {set_clause}
            WHERE id = %s
            RETURNING *;
        """
        
        return self.db.execute_query(query, params, fetch=True)
    
    def delete_organization(self, organization_id):
        """Delete a organization"""
        query = """
            DELETE FROM organizations
            WHERE id = %s
            RETURNING id;
        """
        params = (organization_id,)
        return self.db.execute_query(query, params, fetch=True)
    