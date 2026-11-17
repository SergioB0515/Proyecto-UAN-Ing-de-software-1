# Changelog

## 3.1.0

### Nuevo
- **Disponibilidad del agente**: cada agente puede declararse ausente con una ventana de fechas (desde / hasta, o hasta nuevo aviso) y un motivo opcional, desde su propio perfil o desde la ficha del agente en `/admin/usuarios`. La disponibilidad se deriva siempre de esa ventana, no de una bandera aparte. Un agente ausente deja de aparecer en las sugerencias de asignación, deja de ser destino válido de una transferencia y deja de contar para la cobertura de su área; los tickets que ya tenía asignados no se tocan.
- **Alertas de SLA al área**: cuando un ticket próximo a vencer o vencido no tiene agente asignado, el aviso va a los agentes activos y disponibles de su área. Si el área se quedó sin nadie disponible, el aviso sube al administrador. Antes, un ticket sin dueño solo avisaba a su creador y el equipo de soporte no se enteraba.
- **Cola priorizada por riesgo**: la vista de tickets del área se ordena por defecto por cercanía al vencimiento (porcentaje de SLA consumido) en vez de solo por prioridad, con el orden anterior disponible en el selector *Orden*. La tabla muestra el SLA consumido de cada ticket. El agente sigue eligiendo qué tomar; el sistema solo deja de esconder lo urgente.
- **Escalamiento por edad sin asignar**: un ticket que consume más del 50 % de su plazo sin agente se escala una sola vez al administrador (`UMBRAL_SIN_ASIGNAR` en `app/services/gestor_sla.py`).
- **Vista de cobertura** (`/admin/cobertura`): tickets sin asignar ordenados por SLA consumido, cobertura de cada área (agentes activos, disponibles, ausentes y trabajo pendiente) y lista de agentes ausentes.
- Filtro **Agentes ausentes** en `/admin/usuarios` y distintivo de ausencia en el listado y en la ficha del agente.

### Cambios
- `app/services/disponibilidad.py`: servicio nuevo con la regla de disponibilidad, el filtro SQL equivalente y los conteos de cobertura.
- `ServicioMetricas.sugerir_agente` y `detalle_sugerencia_agente` ya no proponen agentes ausentes.
- `ServicioTickets.listar_tickets_por_area` acepta `orden="prioridad"` (comportamiento histórico, por defecto en el servicio) u `orden="riesgo"`.
- Columnas nuevas: `usuarios.ausente_desde`, `usuarios.ausente_hasta`, `usuarios.motivo_ausencia` y `tickets.notificado_sin_asignar`. Las añade `python init_db.py` sin pérdida de datos.
- Acciones de auditoría nuevas: `marcar_ausente` y `marcar_disponible`.
- 30 pruebas nuevas en `tests/test_disponibilidad.py`.

### Pendiente
- `messages.pot` no se regeneró: las 64 cadenas nuevas se anexaron traducidas a `app/translations/en/LC_MESSAGES/messages.po`. Conviene correr `pybabel extract -F babel.cfg -o messages.pot .` al cerrar la versión.
- El caso de un ticket **ya asignado** a un agente que después se marca ausente sigue avisando solo a ese agente. Es el mismo hueco que esta versión cerró para los tickets sin dueño, pero no estaba en el alcance acordado.

## 3.0.0

### Nuevo
- **Base de conocimiento** (`/conocimiento`): artículos con formato (títulos, listas, código, notas, enlaces), categorías, etiquetas, borradores, búsqueda, orden por recientes/más vistos/más útiles, votos de utilidad, artículos relacionados y vista previa al editar.
- **Sugerencias al crear un ticket**: mientras el usuario escribe se proponen guías relacionadas (puntuación por coincidencia de términos en título, etiquetas, resumen y contenido, con bonificación por categoría estimada). Si una guía resuelve el problema se registra como ticket evitado.
- **Adjuntos** en tickets y comentarios: lista blanca de formatos, verificación de la firma del archivo, 5 MB por archivo y 10 por ticket, almacenamiento fuera de `static/` y descarga solo para quien puede ver el ticket. Arrastrar y soltar y pegar capturas con Ctrl + V.
- **Notas internas** visibles solo para agentes y administradores.
- **Respuestas rápidas** privadas o compartidas, con variables `{nombre}`, `{ticket}`, `{agente}` y `{categoria}`, insertables desde la conversación.
- **Seguidores de tickets** con avisos de nuevos comentarios y cambios de estado.
- **Notificaciones de conversación**: el solicitante recibe aviso (y correo) cuando soporte responde y el agente cuando el solicitante contesta.
- **Encuesta de satisfacción** de 1 a 5 estrellas al cerrarse un ticket, con recordatorio en el panel del usuario.
- **Analítica** (`/analitica`): KPIs con variación contra el periodo anterior, volumen diario, pendientes por día, primera respuesta, MTTR, SLA por categoría, mapa de calor por día y hora, ranking de agentes, CSAT y uso de la base de conocimiento. Exportación a CSV.
- **Gestión de usuarios** (`/admin/usuarios`): búsqueda, filtros, edición de rol/área/nivel, activación y desactivación, desbloqueo, envío de enlace de recuperación y restablecimiento de la verificación en dos pasos, con salvaguardas (no quitarse el propio rol, conservar al menos un administrador activo, no mover agentes con tickets en curso).
- **API REST v1** con tokens personales (hash SHA-256, caducidad, revocación, máximo 5 activos, 120 peticiones por minuto) y documentación en `/api/docs`.
- Endpoint `/salud`, cabeceras de seguridad, cookies de sesión `HttpOnly`/`SameSite`, sesión con caducidad, límite de tamaño de petición y página de error 413.
- `render.yaml` para despliegue.

### Cambios
- `python init_db.py` actualiza bases existentes (tablas, columnas y valores de enums en Postgres) sin pérdida de datos; también se ejecuta al arrancar (`MIGRAR_AL_INICIAR`).
- Tras crear un ticket se abre su detalle.
- Los agentes desactivados no reciben sugerencias de asignación ni transferencias.
- Las etiquetas de categoría y prioridad del mensaje de creación aparecen traducidas.
- Las notificaciones de apelaciones ahora se traducen al inglés.

### Seguridad
- El detalle de un ticket solo es accesible para su creador, los agentes del área o asignados, los seguidores, el agente destino de una transferencia pendiente y los administradores. Antes cualquier usuario autenticado podía abrir y comentar cualquier ticket conociendo su número.
- Las cuentas desactivadas pierden la sesión activa y el acceso a la API de inmediato.

## 2.x
- Rediseño completo de la interfaz, paleta de comandos, atajos de teclado y mejoras de usabilidad.
- Verificación en dos pasos (TOTP) con códigos de respaldo.
- Recuperación de contraseña por correo.
