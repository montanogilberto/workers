"""
Database utilities for Azure SQL Database connections.

This module provides enhanced connection handling with retry logic,
connection pooling support, and proper error handling.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

import pyodbc
from pyodbc import Error as PyodbcError

# Configure module logger
logger = logging.getLogger(__name__)

# Configuration constants
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0


class DatabaseConnectionError(Exception):
    """Custom exception for database connection failures."""
    pass


class DatabaseExecutionError(Exception):
    """Custom exception for database execution failures."""
    pass


def get_connection_string() -> str:
    """
    Get the Azure SQL connection string from environment.
    
    Returns:
        str: The connection string.
        
    Raises:
        DatabaseConnectionError: If the connection string is not configured.
    """
    conn_str = os.getenv("AZURE_SQL_CONNECTION_STRING")
    if not conn_str:
        error_msg = "Missing AZURE_SQL_CONNECTION_STRING in environment variables."
        logger.error(error_msg)
        raise DatabaseConnectionError(error_msg)
    return conn_str


def _execute_with_retry(
    conn: pyodbc.Connection,
    query: str,
    params: tuple = None,
    max_retries: int = MAX_RETRIES
) -> List[Dict[str, Any]]:
    """
    Execute a database query with retry logic.
    
    Args:
        conn: pyodbc connection object.
        query: SQL query to execute.
        params: Query parameters (optional).
        max_retries: Maximum number of retry attempts.
        
    Returns:
        List of dictionaries representing the result rows.
        
    Raises:
        DatabaseExecutionError: If the query fails after all retries.
    """
    retry_count = 0
    current_delay = INITIAL_RETRY_DELAY

    while retry_count <= max_retries:
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description] if cursor.description else []
            conn.commit()
            
            return [dict(zip(cols, r)) for r in rows]
            
        except PyodbcError as e:
            retry_count += 1
            if retry_count > max_retries:
                error_msg = f"Database query failed after {max_retries} attempts: {str(e)}"
                logger.error(error_msg)
                raise DatabaseExecutionError(error_msg)
            
            logger.warning(
                f"Database query failed (attempt {retry_count}/{max_retries}): {str(e)}. "
                f"Retrying in {current_delay:.1f} seconds..."
            )
            time.sleep(current_delay)
            current_delay = min(
                current_delay * RETRY_BACKOFF_MULTIPLIER,
                MAX_RETRY_DELAY
            )


@contextmanager
def get_conn():
    """
    Context manager for database connections with automatic retry.
    
    Yields:
        pyodbc.Connection: Database connection object.
        
    Handles connection creation, validation, and proper closure.
    """
    conn = None
    retry_count = 0
    current_delay = INITIAL_RETRY_DELAY

    while retry_count <= MAX_RETRIES:
        try:
            conn_str = get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=30)
            
            # Validate connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            logger.debug("Database connection established successfully")
            break
            
        except PyodbcError as e:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
            
            retry_count += 1
            if retry_count > MAX_RETRIES:
                error_msg = (
                    f"Failed to establish database connection after {MAX_RETRIES} attempts: "
                    f"{str(e)}"
                )
                logger.error(error_msg)
                raise DatabaseConnectionError(error_msg)
            
            logger.warning(
                f"Database connection failed (attempt {retry_count}/{MAX_RETRIES}): "
                f"{str(e)}. Retrying in {current_delay:.1f} seconds..."
            )
            time.sleep(current_delay)
            current_delay = min(
                current_delay * RETRY_BACKOFF_MULTIPLIER,
                MAX_RETRY_DELAY
            )

    try:
        yield conn
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Database connection closed")
            except Exception as e:
                logger.warning(f"Error closing database connection: {str(e)}")


def exec_sp_json(sp_name: str, payload: dict) -> List[Dict[str, Any]]:
    """
    Executes a stored procedure with JSON payload.
    
    Args:
        sp_name: Name of the stored procedure (e.g., 'dbo.sp_publishJobs').
        payload: Dictionary to be converted to JSON and passed as parameter.
        
    Returns:
        List of dictionaries representing the result rows.
        
    Raises:
        DatabaseExecutionError: If the stored procedure execution fails.
    """
    try:
        pjson = json.dumps(payload, ensure_ascii=False)
        
        with get_conn() as conn:
            return _execute_with_retry(
                conn,
                f"EXEC {sp_name} ?",
                (pjson,)
            )
            
    except DatabaseConnectionError:
        raise
    except Exception as e:
        error_msg = f"Failed to execute stored procedure {sp_name}: {str(e)}"
        logger.error(error_msg)
        raise DatabaseExecutionError(error_msg)
    
    
def query_rows(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query (or EXEC that returns rows) and return rows as dicts.
    Uses the same retry logic and connection handling.
    """
    try:
        with get_conn() as conn:
            return _execute_with_retry(conn, query, params)
    except DatabaseConnectionError:
        raise
    except Exception as e:
        error_msg = f"Failed to run query: {str(e)}"
        logger.error(error_msg)
        raise DatabaseExecutionError(error_msg)


def query_one(query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
    """
    Returns the first row (dict) or None.
    """
    rows = query_rows(query, params)
    return rows[0] if rows else None



def exec_sp_json_many(sp_name: str, payloads: List[dict]) -> List[List[Dict[str, Any]]]:
    """
    Executes a stored procedure multiple times with different payloads.
    
    Args:
        sp_name: Name of the stored procedure.
        payloads: List of dictionaries to execute.
        
    Returns:
        List of result lists for each execution.
    """
    results = []
    for payload in payloads:
        try:
            result = exec_sp_json(sp_name, payload)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to execute {sp_name} for payload: {str(e)}")
            results.append([])
    return results


# Connection pool configuration (for future use)
CONNECTION_POOL_CONFIG = {
    "min_size": 1,
    "max_size": 10,
    "timeout": 300  # seconds
}


def get_pooled_connection():
    """
    Get a connection from the connection pool.
    
    Note: This is a placeholder for future connection pooling implementation.
    For now, it returns a regular connection. In production, consider using
    a connection pool library like SQLAlchemy or a dedicated pool manager.
    
    Returns:
        pyodbc.Connection: Database connection object.
    """
    conn_str = get_connection_string()
    return pyodbc.connect(conn_str, timeout=30)

