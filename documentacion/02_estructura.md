# Estructura del proyecto

## Organización de carpetas

```
proyecto/
├── app/
│   ├── __init__.py          # create_app(): arma la aplicación Flask
│   ├── extensions.py        # instancia de SQLAlchemy (db)
│   ├── models/               # entidades de datos (sin lógica de negocio)
│   │   ├── enums.py          # Categoria, RolUsuario, NivelUsuario, Prioridad, EstadoTicket
│   │   ├── usuario.py
│   │   ├── ticket.py
│   │   ├── comentario.py
│   │   └── log_auditoria.py
│   ├── services/              # lógica de negocio, separada de los modelos
│   │   └── autenticacion.py   # ServicioAutenticacion
│   ├── templates/             # vistas HTML (Jinja2)
│   └── static/                 # CSS/JS
├── instance/
│   └── proyecto.db             # base de datos SQLite (generada, no se versiona)
├── tests/                       # pruebas manuales/automatizadas
├── docs/                        # esta documentación
├── init_db.py                   # script para crear las tablas
├── requirements.txt
└── .gitignore
```

## Componentes principales

| Componente | Responsabilidad |
|---|---|
| `app/models/` | Entidades de datos: `Usuario`, `Ticket`, `Comentario`, `LogAuditoria`. Solo almacenan estado, sin lógica de negocio. |
| `app/services/` | Lógica de negocio separada de las entidades, siguiendo el principio de responsabilidad única. Contiene `ServicioAutenticacion`, y próximamente `ClasificadorTickets` y `GestorSLA`. |
| `app/extensions.py` | Instancia única de SQLAlchemy (`db`), compartida por todos los modelos y servicios sin generar dependencias circulares. |
| `app/__init__.py` | Función `create_app()`: arma la aplicación Flask, conecta la base de datos, registra los modelos. |
| `init_db.py` | Script que se corre una sola vez (o cada vez que se reinicia el esquema) para crear las tablas en SQLite. |

## Por qué esta organización

Se separan `models/` (datos) de `services/` (comportamiento) para que ninguna entidad mezcle almacenamiento de estado con reglas de negocio — esto permite probar la lógica de clasificación, autenticación o cálculo de SLA de forma aislada, sin necesidad de una base de datos completa montada.
