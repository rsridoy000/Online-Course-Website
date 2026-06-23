import psycopg2
import sys

db_url = "postgresql://neondb_owner:npg_cAtom0jXEY8y@ep-curly-tree-ao9i5ghm.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

print("Attempting to connect to the Neon database...")
try:
    conn = psycopg2.connect(db_url, connect_timeout=5)
    print("Connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print("Database version:", db_version)
    cursor.close()
    conn.close()
except Exception as e:
    print("Connection failed!", file=sys.stderr)
    print("Error:", e, file=sys.stderr)
