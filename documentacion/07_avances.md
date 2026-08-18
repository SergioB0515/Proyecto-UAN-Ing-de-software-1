# Avances del proyecto

*Este documento se actualiza al cierre de cada sprint. Cada entrada describe qué se completó, no solo qué se intentó.*

## Sprint 1 — en curso

**Completado:**
- Definición del modelo de datos (`Usuario`, `Ticket`, `Comentario`, `LogAuditoria`) y del diagrama de clases.
- Implementación de los 4 modelos con SQLAlchemy, incluyendo enumeraciones (`Categoria`, `RolUsuario`, `NivelUsuario`, `Prioridad`, `EstadoTicket`) y llaves foráneas.
- Configuración de `create_app()` y conexión de la base de datos SQLite.
- Creación y verificación de las tablas en la base de datos real.
- `ServicioAutenticacion`: generación y verificación de hash de contraseña con bcrypt, probadas con casos reales (contraseña correcta/incorrecta).

**En progreso:**
- `ServicioAutenticacion`: método de registro de usuarios y control de bloqueo por intentos fallidos.
- CRUD básico de tickets.

**Pendiente para cerrar el sprint:**
- Rutas de Flask para registro/inicio de sesión.
- Pruebas manuales del flujo de autenticación completo.

## Sprint 2 — no iniciado

Pendiente: algoritmo de clasificación, ajuste de prioridad por nivel VIP, cálculo de SLA y recordatorios.

## Sprint 3 — no iniciado

Pendiente: módulo de auditoría, bloqueo por fuerza bruta, panel de métricas.

## Sprint 4 — no iniciado

Pendiente: integración final, corrección de errores, documentación de cierre.
