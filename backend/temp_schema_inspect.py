import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = [row[0] for row in cursor.fetchall()]
    print('Tables:', tables)
    # For each table, list columns
    for tbl in tables:
        cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' AND table_schema='public';")
        cols = cursor.fetchall()
        print(f'-- {tbl} columns:')
        for col in cols:
            print('   ', col[0], col[1])

