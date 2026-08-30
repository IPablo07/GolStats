# División del trabajo y flujo de ramas

Somos tres. Cada uno trabaja en su propia rama y abre un Pull Request hacia
`main`. Nadie edita archivos de otro: así no chocamos al mergear.

## Quién hace qué

| Persona | Rama | Archivos que le pertenecen |
|---|---|---|
| **Pablo** | `feature/poo` | `modelos/`, `servicios/`, `datos_prueba.py`, `app.py`, `prueba_modelos.py` |
| **Wil** | `feature/web` | `templates/`, `static/css/`, `static/js/`, `prueba_rutas.py` |
| **Marco** | `feature/bd-huella` | `sql/`, capa de persistencia, integración real del lector SecuGen |

Archivos compartidos que ya están en `main` y **nadie modifica sin avisar**:
`config.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.

## Orden de los Pull Requests

```
main
 └── PR #1  feature/poo    (Pablo)  → clases del dominio, servicios y rutas
      └── PR #2  feature/web   (Wil)    → plantillas, estilos y JavaScript
           └── PR #3  feature/bd-huella (Marco) → PostgreSQL + lector real
```

Primero entra el de Pablo, porque las plantillas de Wil consumen sus rutas y sus
clases. Wil puede empezar antes de que se mergee ramificando de `feature/poo`
y haciendo `git rebase main` cuando el PR #1 entre.

Marco va último: reemplaza `datos_prueba.py` (datos en memoria) por PostgreSQL
sin cambiar la interfaz que usan las rutas, y conecta el lector de huella real.

## Comandos de siempre

```bash
git checkout main
git pull origin main
git checkout -b feature/<lo-tuyo>
# ... trabajar ...
git add <solo tus archivos>
git commit -m "Descripcion de lo que hiciste"
git push -u origin feature/<lo-tuyo>
```

Después se abre el Pull Request desde GitHub.

**Nunca uses `git add .`** mientras tengas en la carpeta archivos de otro
compañero: te los vas a llevar en tu commit. Agregá siempre tus rutas explícitas.

## Estado actual

- [x] `main` — estructura base
- [x] `feature/poo` — clases del dominio, servicios y rutas (listo para PR)
- [ ] `feature/web` — plantillas, estilos y JavaScript
- [ ] `feature/bd-huella` — PostgreSQL + SecuGen
