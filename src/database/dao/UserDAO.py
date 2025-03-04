from database.dbutil import Database

class UserDAO:
    def __init__(self):
        self.db = Database()

    def __enter__(self):
        if self.db:
            self.db.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db: self.db.close()        
        
    def get_user(self, user_id):
        """Get a user by its ID"""
        query = """
            SELECT * FROM users 
            WHERE id = %s
        """
        params = (user_id,)
        return self.db.execute_query(query, params, fetch=True)
    
    def create_user(self, organization_id, email):
        """Create a new user"""
        query = """
            INSERT INTO users (organization_id, email)
            VALUES (%s, %s)
            RETURNING *
        """
        params = (organization_id, email)
        return self.db.execute_query(query, params, fetch=True)
    
    def update_user(self, user_id, organization_id=None, email=None):
        """Update an existing user"""
        # Build dynamic query based on provided parameters
        set_clauses = []
        params = []
        
        if organization_id is not None:
            set_clauses.append("organization_id = %s")
            params.append(organization_id)
        
        if email is not None:
            set_clauses.append("email = %s")
            params.append(email)
                       
        if not set_clauses:
            return None  # Nothing to update
            
        set_clause = ", ".join(set_clauses)
        params.append(user_id)  # For the WHERE clause
        
        query = f"""
            UPDATE users
            SET {set_clause}
            WHERE id = %s
            RETURNING *
        """
        
        return self.db.execute_query(query, params, fetch=True)
    
    def delete_user(self, user_id):
        """Delete a user"""
        query = """
            DELETE FROM users
            WHERE id = %s
            RETURNING id
        """
        params = (user_id,)
        return self.db.execute_query(query, params, fetch=True)
    
    def get_users_by_organization(self, organization_id):
        """Get all users for an organization"""
        query = """
            SELECT * FROM users
            WHERE organization_id = %s
            ORDER BY created_at DESC
        """
        params = (organization_id,)
        return self.db.execute_query(query, params, fetch=True)