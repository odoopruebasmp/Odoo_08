# pylint: disable=no-utf8-coding-comment, translation-required
"""
Database utilities
"""
import psycopg2
from contextlib import contextmanager


@contextmanager
def create_cursor(cursor_info):
    """
    Create a new detached cursor based on input cursor parameters
    @params:
        cursor_info: dictionary of connection parameters
    @return:
        cursor (psycopg2.extensions.cursor)
    """
    # cursor_info = cursor._cnx.info
    db_host = cursor_info.get('host', 'localhost')
    db_port = cursor_info.get('port', 5432)
    db_user = cursor_info.get('user', 'odoo')
    db_password = cursor_info.get('password', '')
    db_name = cursor_info.get('dbname', 'postgres')
    conn = psycopg2.connect(
        user=db_user, host=db_host, port=db_port,
        password=db_password, dbname=db_name
    )
    try:
        yield conn.cursor()
    finally:
        conn.close()
