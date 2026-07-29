import psycopg
from pgvector.psycopg import register_vector

from common.config import settings


def get_connection() -> psycopg.Connection:
    conn = psycopg.connect(settings.database_url)
    register_vector(conn)   # teaches psycopg to convert numpy/list <-> vector type
    return conn