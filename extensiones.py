"""
extensiones.py
────────────────
Instancias compartidas (SQLAlchemy y Flask-Mail) en su propio módulo para
evitar imports circulares: app.py crea la app y las inicializa con
`init_app(app)`, y el resto del proyecto las importa desde aquí sin tener
que importar app.py.
"""

from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

#: Envío de correo. Sin esta instancia, ServicioCorreo se queda siempre en
#: modo simulado por mucho que el .env tenga servidor configurado.
mail = Mail()
