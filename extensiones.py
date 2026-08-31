"""
extensiones.py
────────────────
Instancias compartidas (por ahora, solo SQLAlchemy) en su propio módulo
para evitar imports circulares: app.py crea la app y llama a
`db.init_app(app)`, y los modelos importan `db` desde aquí sin tener que
importar app.py.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
