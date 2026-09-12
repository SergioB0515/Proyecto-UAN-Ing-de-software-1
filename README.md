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

### 3. Base de datos

```bash
python init_db.py
```

Datos iniciales (opcional, cada script se salta si ya existe el dato):

```bash
python -m app.scripts.seed_admin          # admin inicial
python -m app.scripts.seed_demo           # usuarios, agentes y tickets de ejemplo
python -m app.scripts.seed_palabras_clave # palabras clave para el clasificador
```

### 4. Correr la aplicación

```bash
python -m app.app
```

Por defecto sirve en `http://localhost:5050`.

### 5. Pruebas

```bash
pytest
```

## Estructura del proyecto

```
app/
  models/        modelos de SQLAlchemy
  routes/        blueprints (auth, tickets, metricas, auditoria, solicitudes)
  services/      lógica de negocio (un servicio por dominio)
  templates/     plantillas Jinja2
  static/        CSS y archivos estáticos
  scripts/       scripts de datos (admin/demo/palabras clave/entrenamiento ML)
  translations/  catálogos de traducción (Flask-Babel)
  ml_artifacts/  modelo de clasificación entrenado
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
