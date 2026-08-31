# Estructura del proyecto

## Organización de carpetas

```
proyecto/
├── app/
│   ├── app.py                  # Punto de entrada: crea la app y la corre (app.run)
│   ├── __init__.py             # create_app(): arma la aplicación Flask, registra blueprints
│   ├── config.py                # Config: SECRET_KEY, SQLALCHEMY_DATABASE_URI
│   ├── extensions.py            # Instancia única de SQLAlchemy (db)
│   ├── models/                   # Entidades de datos (sin lógica de negocio)
│   │   ├── enum.py                # Categoria, RolUsuario, NivelUsuario, Prioridad,
│   │   │                          # EstadoTicket, AccionAuditoria
│   │   ├── usuario.py
│   │   ├── ticket.py
│   │   ├── comentario.py
│   │   └── log_auditoria.py
│   ├── routes/                    # Blueprints de Flask (vistas HTTP)
│   │   ├── __init__.py
│   │   ├── auth.py                 # /login, /logout, /registro, /dashboard
│   │   ├── tickets.py               # /tickets/crear, /tickets/area/<area>,
│   │   │                            # /tickets/<id>/cambiar-estado,
│   │   │                            # /tickets/<id>/reasignar, /tickets/<id>
│   │   └── decoradores.py           # @requiere_login, @requiere_admin
│   ├── services/                    # Lógica de negocio, separada de los modelos
│   │   ├── autenticacion.py          # ServicioAutenticacion
│   │   ├── clasificador.py           # ClasificadorTickets
│   │   ├── gestor_sla.py             # GestorSLA
│   │   ├── tickets.py                # ServicioTickets (crear, cambiar estado,
│   │   │                             # reasignar, comentar)
│   │   ├── auditoria.py              # ServicioAuditoria
│   │   ├── metricas.py               # ServicioMetricas
│   │   └── exceptions.py             # Excepciones de negocio (ver tabla abajo)
│   ├── scripts/
│   │   └── seed_admin.py             # Crea el usuario admin inicial (no crea tablas)
│   └── Templates/                    # Vistas HTML (Jinja2)
│       ├── base.html
│       ├── login.html
│       ├── registro.html
│       ├── crear_ticket.html
│       ├── tickets_por_area.html
│       ├── ticket_detalle.html
│       └── dashboard.html
├── instance/
│   └── proyecto.db                   # Base de datos SQLite (generada, no se versiona)
├── tests/                            # Pruebas manuales (scripts ejecutables con `python -m`)
│   ├── __init__.py
│   ├── test_registro.py
│   ├── test_login.py
│   ├── test_clasificador.py
│   ├── test_tickets.py
│   ├── test_sla.py
│   └── test_metricas.py
├── documentacion/                    # esta documentación
├── init_db.py                        # Script que crea las tablas (db.create_all())
└── .gitignore
```


| Componente | Responsabilidad |
|---|---|
| `app/models/` | Entidades de datos: `Usuario`, `Ticket`, `Comentario`, `LogAuditoria`. Solo almacenan estado, sin lógica de negocio. |
| `app/services/` | Lógica de negocio separada de las entidades, siguiendo el principio de responsabilidad única. Contiene `ServicioAutenticacion`, `ClasificadorTickets`, `GestorSLA`, `ServicioTickets`, `ServicioAuditoria` y `ServicioMetricas`. |
| `app/routes/` | Blueprints de Flask que exponen la lógica de negocio como vistas HTTP: `auth_bp` (autenticación y dashboard) y `tickets_bp` (ciclo de vida de tickets). `decoradores.py` centraliza el control de acceso (`@requiere_login`, `@requiere_admin`). |
| `app/extensions.py` | Instancia única de SQLAlchemy (`db`), compartida por todos los modelos y servicios sin generar dependencias circulares. |
| `app/__init__.py` | Función `create_app()`: arma la aplicación Flask, conecta la base de datos, registra los blueprints. |
| `app.py` | Punto de entrada de la aplicación (`app.run(debug=True)`). |
| `app/scripts/seed_admin.py` | Crea el usuario administrador inicial (`admin@empresa.com`) si no existe. No crea las tablas. |
| `init_db.py` | Script en la raíz del proyecto que corre `db.create_all()` para crear las tablas en SQLite. Se ejecuta una sola vez (o cada vez que se reinicia el esquema), **antes** de `seed_admin.py`. |

## Por qué esta organización

Se separan `models/` (datos) de `services/` (comportamiento) para que ninguna entidad mezcle
almacenamiento de estado con reglas de negocio — esto permite probar la lógica de
clasificación, autenticación o cálculo de SLA de forma aislada, sin necesidad de una base de
datos completa montada.
