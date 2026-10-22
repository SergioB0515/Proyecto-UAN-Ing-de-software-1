# Sistema de Tickets IT

Sistema de gestión de incidencias (tickets) para el área de soporte de TI de una
empresa. Cualquier empleado puede reportar un problema en texto libre; el sistema lo
clasifica automáticamente, lo enruta al área de soporte correspondiente, le asigna una
prioridad, y da seguimiento a su resolución mediante plazos de atención (SLA),
notificaciones en tiempo real y un registro de auditoría de seguridad.

Proyecto académico de Ingeniería de Software. La documentación completa (requisitos,
arquitectura, historias de usuario, avances por sprint/versión y evidencias) vive en
[`documentacion/`](documentacion/).

## Funcionalidades principales

- **Autenticación y roles**: usuario final, agente y administrador, con contraseñas
  hasheadas (bcrypt), política de contraseñas, CSRF en formularios, y bloqueo por
  intentos fallidos tanto por usuario como por IP.
- **Ciclo de vida de tickets**: creación, clasificación automática por categoría
  (palabras clave o un clasificador de ML opcional), prioridad base y ajuste por nivel
  del solicitante (VIP/normal), asignación a un agente, cambio de estado, comentarios
  y cierre.
- **SLA**: cálculo de la fecha límite de atención según prioridad y nivel, con
  verificación periódica (scheduler) de tickets vencidos o próximos a vencer.
- **Transferencias entre agentes**: solicitud de reasignación agente-a-agente,
  escalamiento a otra área y cambio de prioridad, cada una con su propio flujo de
  aprobación/rechazo.
- **Notificaciones en tiempo real** (Socket.IO): campanita en la navbar con badge en
  vivo, traducidas al idioma de quien las lee.
- **Internacionalización** (Flask-Babel): interfaz disponible en español e inglés.
- **Panel de métricas y auditoría**: métricas agregadas con drill-down a los tickets
  detrás de cada número, log de auditoría filtrable, y exportación a CSV/Excel de
  tickets, métricas y auditoría.
- **Perfil de usuario**: cambio de contraseña y nombre, foto de perfil, estadísticas
  personales.
- **Verificación en dos pasos y recuperación de contraseña**: TOTP compatible con
  cualquier app autenticadora, códigos de respaldo de un solo uso y enlaces de
  recuperación con caducidad.
- **Base de conocimiento**: artículos con categorías, etiquetas, búsqueda, votos de
  utilidad y borradores. Al escribir un ticket se sugieren guías relacionadas y el
  usuario puede marcar su problema como resuelto sin abrir el ticket.
- **Colaboración en tickets**: adjuntos validados por tipo y contenido, notas internas
  visibles solo para el equipo, respuestas rápidas con variables y seguidores que
  reciben avisos de la actividad.
- **Encuesta de satisfacción (CSAT)** al cerrarse cada ticket.
- **Analítica**: volumen diario, pendientes, tiempo de primera respuesta y de
  resolución, cumplimiento de SLA por categoría, mapa de calor por hora, ranking de
  agentes y satisfacción, comparados con el periodo anterior y exportables a CSV.
- **Gestión de usuarios**: búsqueda y filtros, edición de rol/área/nivel, activación y
  desactivación de cuentas, desbloqueo, envío de enlaces de recuperación y
  restablecimiento de la verificación en dos pasos.
- **API REST v1** con tokens personales (guardados como hash, con caducidad, revocables
  y con límite de peticiones) y documentación integrada en `/api/docs`.
- **Clasificación por ML (opcional)**: clasificador basado en embeddings multilingües
  + palabras clave ponderadas + detección de casi-duplicados, con revisión manual para
  los casos de baja confianza.

## Stack técnico

- **Backend**: Flask, SQLAlchemy (Flask-SQLAlchemy)
- **Frontend**: Jinja2 + Bootstrap 5 (sin framework adicional)
- **Tiempo real**: Flask-SocketIO
- **i18n**: Flask-Babel (es/en)
- **Seguridad**: Flask-WTF (CSRF), bcrypt
- **Tareas en segundo plano**: APScheduler
- **ML**: scikit-learn, sentence-transformers, pandas
- **Pruebas**: pytest
- **CI**: GitHub Actions (corre la suite de pytest en cada push/PR a `main`)

## Puesta en marcha

### 1. Entorno virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Variables de entorno

La app exige `SECRET_KEY` por variable de entorno (falla al arrancar si falta). Crea un
archivo `.env` en la raíz del proyecto:

```bash
SECRET_KEY=<genera-un-valor-con-el-comando-de-abajo>
```

Generar un valor seguro:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Otras variables opcionales (con sus valores por defecto):

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///proyecto.db` | Cadena de conexión de la base de datos |
| `SLA_INTERVALO_MINUTOS` | `30` | Cada cuánto revisa el scheduler los vencimientos de SLA |
| `SCHEDULER_ACTIVO` | `1` | Activa/desactiva el scheduler en segundo plano |
| `CLASIFICADOR_ML_ACTIVO` | `0` | Activa el clasificador por ML en vez del de palabras clave |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | — | Credenciales del admin inicial (ver script de seed) |
| `CARPETA_ADJUNTOS` | `instance/adjuntos` | Carpeta donde se guardan los archivos adjuntos |
| `MAX_CONTENT_MB` | `26` | Tamaño máximo de una petición (varios adjuntos juntos) |
| `MIGRAR_AL_INICIAR` | `1` | Al arrancar crea tablas y columnas nuevas que falten |
| `SESSION_COOKIE_SECURE` | `0` | Ponlo en `1` en producción con HTTPS |
| `SESION_HORAS` | `8` | Duración de la sesión iniciada |
| `APP_BASE_URL` | `http://localhost:5000` | URL pública usada en los enlaces de los correos |

### 3. Base de datos

```bash
python init_db.py
```

`init_db.py` también actualiza una base existente: crea las tablas nuevas y agrega las
columnas que falten sin borrar datos (en Postgres además sincroniza los valores de los
enums). Puede ejecutarse cuantas veces sea necesario.

Datos iniciales (opcional, cada script se salta si ya existe el dato):

```bash
python -m app.scripts.seed_admin          # admin inicial
python -m app.scripts.seed_demo           # usuarios, agentes y tickets de ejemplo
python -m app.scripts.seed_palabras_clave # palabras clave para el clasificador
python -m app.scripts.seed_v3             # artículos, respuestas rápidas y encuestas de ejemplo
```

### 4. Correr la aplicación

```bash
python -m app.app
```

Por defecto sirve en `http://localhost:5050`. El endpoint `/salud` devuelve el estado
del servicio y de la base de datos (útil como health check en el despliegue).

### Despliegue

`render.yaml` define el servicio web (gunicorn con un worker y varios hilos, necesario
para Socket.IO) y una base Postgres. En plataformas con disco efímero, los adjuntos
deben apuntar a un disco persistente mediante `CARPETA_ADJUNTOS`.

### 5. Pruebas

```bash
pytest
```

## Estructura del proyecto

```
app/
  models/        modelos de SQLAlchemy
  routes/        blueprints (auth, tickets, metricas, auditoria, solicitudes, seguridad,
                 usuarios, conocimiento, colaboracion, analitica, api)
  services/      lógica de negocio (un servicio por dominio)
  templates/     plantillas Jinja2
  static/        CSS y archivos estáticos
  scripts/       scripts de datos (admin/demo/palabras clave/entrenamiento ML)
  translations/  catálogos de traducción (Flask-Babel)
  ml_artifacts/  modelo de clasificación entrenado
  migraciones.py actualización de esquema sin pérdida de datos
tests/           suite de pytest
documentacion/   documentación del proyecto (requisitos, arquitectura, avances)
```

## Internacionalización

Para regenerar los catálogos de traducción tras agregar o cambiar textos:

```bash
pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d app/translations -l en
pybabel compile -d app/translations -l en
```

## API

Crea un token en **Menú de usuario → API y tokens** y envíalo en cada petición:

```bash
curl -H "Authorization: Bearer tk_..." http://localhost:5050/api/v1/tickets?estado=abierto
```

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/yo` | Usuario del token |
| GET | `/api/v1/tickets` | Lista paginada con filtros |
| POST | `/api/v1/tickets` | Crear ticket |
| GET | `/api/v1/tickets/{id}` | Detalle con comentarios y adjuntos |
| POST | `/api/v1/tickets/{id}/comentarios` | Comentar |
| GET | `/api/v1/articulos` | Buscar en la base de conocimiento |
| GET | `/api/v1/metricas` | Indicadores (solo administradores) |

Los permisos son los mismos que en la web. Ver `CHANGELOG.md` para el historial de versiones.
