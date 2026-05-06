"""Add cleanup method to mysql_service.py"""
import re

with open('app/services/mysql_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the location to insert (after batch_upsert_tracked_rows method)
insert_marker = '        self.execute_many(query, params_list)\n        logger.debug(f"Batch upserted {len(rows)} tracked rows")'
        
cleanup_method = '''        
    def cleanup_old_tracking_data(
        self,
        config_id: Optional[int] = None,
        days_to_keep: int = 30,
    ) -> int:
        """
        Clean up old tracking data to prevent unlimited table growth.
        
        Args:
            config_id: If provided, only clean this config's data
            days_to_keep: Number of days of data to keep (default 30)
            
        Returns:
            Number of rows deleted
        """
        query = """
            DELETE FROM change_tracking
            WHERE last_sync_at < DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        params = [days_to_keep]
        
        if config_id is not None:
            query += " AND config_id = %s"
            params.append(config_id)
        
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"Cleaned up {deleted_count} old tracking records (older than {days_to_keep} days)")
            return deleted_count
        except MySQLError as e:
            conn.rollback()
            raise MySQLServiceError(f"MySQL error {e.errno}: {e.msg}") from e
        finally:
            if cursor:
                cursor.close()
            conn.close()

'''

if insert_marker in content:
    # Insert after the marker
    insert_pos = content.find(insert_marker) + len(insert_marker)
    content = content[:insert_pos] + "\n" + cleanup_method + content[insert_pos:]
    print("Successfully added cleanup_old_tracking_data method")
else:
    print("Could not find insertion point")
    # Debug: print what we're looking for
    idx = content.find('execute_many(query, params_list)')
    if idx > 0:
        print("Found 'execute_many' at index", idx)
        print("Context:", repr(content[idx:idx+200]))
            
with open('app/services/mysql_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
    
print("File updated successfully!")
