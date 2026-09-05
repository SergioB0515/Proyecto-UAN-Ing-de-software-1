# Avances del proyecto

*Este documento se actualiza al cierre de cada sprint. Cada entrada describe qué se completó, no solo qué se intentó.*

## Spike técnico — completado

Evaluación de clasificación por IA con Ollama/llama3, descartada a favor del algoritmo de
reglas por palabras clave. Ver detalle en `05_metodologia.md`.

## Sprint 1 — completado

**Completado:**
- Modelo de datos (`Usuario`, `Ticket`, `Comentario`, `LogAuditoria`) implementado con
  SQLAlchemy, incluyendo enumeraciones (`Categoria`, `RolUsuario`, `NivelUsuario`,
  `Prioridad`, `EstadoTicket`, `AccionAuditoria`) y llaves foráneas.
- `create_app()`, `init_db.py` y conexión de la base de datos SQLite funcionando.
- `ServicioAutenticacion` completo: generación/verificación de hash con bcrypt, registro de
  usuarios (con rol, nivel y área de soporte) y control de bloqueo por intentos fallidos.
- Rutas de Flask para login, logout, registro y dashboard (`app/routes/auth.py`).
- Pruebas manuales de registro y login (`tests/test_registro.py`, `tests/test_login.py`).

## Sprint 2 — completado

**Completado:**
- `ClasificadorTickets`: clasificación por palabras clave, con desempate por orden de
  categoría en el diccionario `PALABRAS_CLAVE`.
- `ServicioTickets.crear_ticket`: asigna categoría, prioridad base por categoría y ajuste de
  prioridad por nivel VIP.
- `GestorSLA`: cálculo de fecha límite según prioridad y nivel de usuario, y verificación de
  tickets vencidos/próximos a vencer.
- CRUD de tickets: crear, listar por área (ordenado por prioridad), cambiar estado, reasignar
  agente, agregar comentarios (`app/routes/tickets.py`, `services/tickets.py`).
- Pruebas manuales de clasificación, SLA y ciclo de vida del ticket (`test_clasificador.py`,
  `test_sla.py`, `test_tickets.py`).

**Nota de cierre posterior:** el recordatorio de vencimiento para el creador del ticket
(RF-07) quedó pendiente en este sprint y se cerró en la versión 1.1 — ver más abajo.

## Sprint 3 — completado

**Completado:**
- `ServicioAuditoria`: registro de acciones críticas (login, registro, creación de ticket,
  cambio de estado, reasignación, comentarios, bloqueo/desbloqueo de cuenta), con reintento
  automático ante fallos de guardado.
- Bloqueo de cuenta tras intentos fallidos de login (umbral ajustado a 3 intentos por
  indicación del profesor; el diseño original tenía 5).
- `ServicioMetricas` y panel de métricas (`/dashboard`): tickets por estado/categoría/prioridad,
  vencidos actuales, próximos a vencer, vencidos en los últimos 30 días, cantidad de agentes.
- Pruebas manuales de métricas (`test_metricas.py`).

**Nota de cierre posterior:** la pantalla para que el administrador consulte el log de
auditoría (RF-10, CU-06) quedó pendiente en este sprint y se cerró en la versión 1.1 — ver
más abajo.

## Sprint 4 — completado

**Completado:**
- Interfaz web completa con Bootstrap 5 (login, registro, crear ticket, listar por área,
  detalle de ticket con comentarios, dashboard de métricas).

## Versión 1.1 — completado

Cierre de los dos pendientes de alcance que quedaron abiertos desde los sprints 2 y 3, más
deuda técnica identificada:

- **RF-07 cerrado:** `GestorSLA.verificar_vencimientos()` ahora acepta un filtro opcional
  por `creador_id`; el dashboard del usuario final llama a este método filtrado por su propio
  id y resalta sus propios tickets vencidos/próximos a vencer, igual que ya ocurría en la
  vista de agente.
- **RF-10 / CU-06 cerrado:** nueva ruta `/auditoria` (blueprint `auditoria_bp`), con filtros
  por usuario, acción y rango de fechas, y paginación (35 registros por página).
- Base de datos de tests aislada de la de desarrollo (`test_proyecto.db` en vez de compartir
  `proyecto.db`), evitando que correr la suite de pruebas contamine datos reales.
- Renombrado `app/Templates/` → `app/templates/` y `app/Static/` → `app/static/` para
  eliminar el riesgo de portabilidad entre sistemas operativos (Git en Windows no detecta
  cambios de solo mayúsculas/minúsculas por defecto; se resolvió con un rename en dos pasos).

## Versión 1.2 — completado

Autoservicio y usabilidad:

- Cambio de contraseña propio, para cualquier rol, con verificación de la contraseña actual.
- Filtros (estado, prioridad, rango de fechas) en `listar_tickets_por_area`, migrado al mismo
  tiempo del estilo `Ticket.query.filter_by(...)` al estilo `select().where()` usado en el
  resto del proyecto.
- Campo `radicado` del modelo `Ticket` eliminado: el documento de requisitos usa la notación
  "id/radicado" tratándolos como sinónimos, y como cada ticket ya está atado a un
  `creador_id` con sesión autenticada, no existe el caso de uso de consulta anónima por
  código (tipo PQRS) que justificaría un identificador público separado del `id`.

## Versión 1.3 — completado

Seguridad:

- Protección CSRF (`Flask-WTF`) en los 6 formularios `POST` de la aplicación.
- Política de contraseñas centralizada en `ServicioAutenticacion.validar_politica_contrasena`
  (mínimo 8 caracteres, al menos una mayúscula, una minúscula, un número y un símbolo),
  aplicada tanto al registro de usuarios como al cambio de contraseña.
- Bloqueo por IP, además del bloqueo por usuario ya existente: se registra cada intento
  fallido de login (`IntentoLoginFallido`, con la IP y el email intentado, exista o no ese
  usuario) y, si 5 **emails distintos** fallan desde la misma IP en una ventana de 1 hora, se
  bloquea esa IP por 3 horas (`IPBloqueada`). El conteo se hace sobre emails distintos, no
  sobre el volumen total de fallos, para no penalizar redes compartidas (ej. una oficina)
  donde un solo usuario equivocándose varias veces con su propia contraseña no debe bloquear
  a sus compañeros.
- Limpieza automática de `IntentoLoginFallido` cada 90 minutos vía `APScheduler`, evitando
  que la tabla crezca indefinidamente con intentos ya fuera de la ventana de detección.

## Versión 1.4 — completado

Observabilidad y perfil de usuario:

- Perfil expandido: datos de cuenta, foto de perfil (subida validada con Pillow —
  extensión, tamaño máximo 2MB y verificación real de que el archivo es una imagen, no solo
  su extensión), cambio de nombre (solo letras y espacios, capitalizado), y estadísticas
  personales (tickets creados; para agentes, también tickets tomados y cerrados).
- Drill-down en el panel de métricas: cada número (por estado, por categoría, por prioridad,
  vencidos actuales, próximos a vencer, vencidos últimos 30 días) es un enlace a una vista
  filtrada de la lista real de tickets detrás de esa cifra.
- Listado administrativo global de tickets (`/admin/tickets`, no limitado a un área), con los
  mismos filtros más una "vista especial" para los 3 casos de drill-down basados en SLA.
- Exportación a CSV y Excel (`openpyxl`) de la lista de tickets filtrada, del resumen de
  métricas, y del log de auditoría filtrado.

## Versión 1.5 — completado

Rediseño visual completo de la interfaz (paleta de colores, tipografía, componentes),
manteniendo Bootstrap 5 como base sin introducir un framework de frontend adicional.

## Versión 1.6 — completado

Calidad y cierre para la entrega:

- Migración completa de los 7 scripts de prueba manuales (`if __name__ == "__main__":` con
  asserts sueltos) a `pytest` real, con fixtures compartidas en `tests/conftest.py`.
- Integración continua con GitHub Actions (`.github/workflows/tests.yml`): la suite completa
  de pytest corre automáticamente en cada `push` y cada Pull Request hacia `main`.
- Corrección de `requirements.txt` (estaba en codificación UTF-16 por un `pip freeze >` hecho
  desde PowerShell, y le faltaba declarar `pytest`/`openpyxl`/`Flask-WTF`/`APScheduler`/
  `Pillow` pese a ya usarse en el código).
