import sqlite3
conn = sqlite3.connect('data/kaelis_graph.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f'Tables: {tables}')

cursor.execute('SELECT COUNT(*) FROM kg_entities')
print(f'Entities: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM kg_triples')
print(f'Triples: {cursor.fetchone()[0]}')

conn.close()
