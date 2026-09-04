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

**Pendiente de este alcance:** el recordatorio de vencimiento sigue siendo visible solo para
agentes (resaltado en la tabla del área), no para el creador del ticket, como pedía RF-07.

## Sprint 3 — completado (parcial)

**Completado:**
- `ServicioAuditoria`: registro de acciones críticas (login, registro, creación de ticket,
  cambio de estado, reasignación, comentarios, bloqueo/desbloqueo de cuenta), con reintento
  automático ante fallos de guardado.
- Bloqueo de cuenta tras 3 intentos fallidos de login, por 5 horas.
- `ServicioMetricas` y panel de métricas (`/dashboard`): tickets por estado/categoría/prioridad,
  vencidos actuales, próximos a vencer, vencidos en los últimos 30 días, cantidad de agentes.
- Pruebas manuales de métricas (`test_metricas.py`).

**Pendiente:** no existe todavía una pantalla para que el administrador consulte el log de
auditoría (RF-10, CU-06). El log se escribe correctamente en la base de datos, pero solo es
accesible por consulta directa a la base de datos, no desde la interfaz web.

## Sprint 4 — en curso

**Completado:**
- Interfaz web completa con Bootstrap 5 (login, registro, crear ticket, listar por área,
  detalle de ticket con comentarios, dashboard de métricas).

**Pendiente para cerrar el sprint:**
- Pantalla de consulta del log de auditoría para el administrador.
- Recordatorio de SLA visible para el creador del ticket, no solo para el agente.
