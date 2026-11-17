# Changelog

## 3.5.0

### Nuevo
- **Pausa de SLA (estado «En espera»)**: un agente puede dejar un ticket en espera del solicitante indicando qué le hace falta. Mientras el ticket está en espera el reloj del SLA se detiene, el ticket no entra en los listados de vencidos ni de próximos a vencer, y al reanudarse la fecha límite se corre exactamente lo que duró la espera. El solicitante recibe aviso en la aplicación y por correo, y el ticket vuelve a atención **solo** que él responda en la conversación: el agente no tiene que reanudarlo a mano. El motivo de la espera queda como comentario público y la auditoría distingue `pausar_sla` de `reanudar_sla`.
- **Cobertura de los tickets de un agente ausente**: al declararse ausente un agente, sus tickets vivos quedan marcados como pendientes de cobertura y el aviso va a los agentes disponibles de su área (al administrador si el área se quedó sin nadie). Cualquier agente disponible del área, o el administrador, puede tomar la cobertura desde `/admin/cobertura`, desde la cola del área o desde el propio ticket, sin pasar por una solicitud de transferencia que el agente ausente tendría que aceptar. Al volver el agente, la marca se limpia. Esto cierra el pendiente que la 3.1 dejó documentado: un ticket ya asignado a un agente que luego se ausentaba seguía avisándole solo a él.
- **Aviso de SLA consciente de la ausencia**: si el ticket vencido o próximo a vencer tiene agente pero ese agente está ausente o inactivo, el aviso también va al área y el ticket se marca para cobertura.
- **Webhooks salientes firmados** (`/admin/webhooks`): hasta 10 destinos HTTP suscritos a los eventos `ticket.creado`, `ticket.asignado`, `ticket.estado_cambiado`, `ticket.cerrado`, `sla.vencido` y `ticket.cobertura_requerida`. Cada envío es un POST con el cuerpo en JSON y la cabecera `X-Tickets-Signature: t=<marca>,v1=<HMAC-SHA256 de «marca.cuerpo»>`, con la marca de tiempo dentro de la firma para que una copia capturada no se pueda reenviar. Incluye bitácora de entregas (código HTTP, intentos, duración, error), reintentos solo de los fallos transitorios (sin respuesta o 5xx), auto-desactivación tras 10 fallos seguidos, envío de prueba y la validación de URL que bloquea destinos de la red interna (SSRF).
- **Búsqueda global** (`/buscar`): tickets por número o por texto, artículos de la base de conocimiento y, para el administrador, cuentas. Cada resultado pasa por el mismo control de acceso que su página, así que la búsqueda no revela tickets que el usuario no puede abrir. Complementa la paleta de comandos (Ctrl + K), que solo navega entre páginas.

### Cambios
- `EstadoTicket.EN_ESPERA` y transiciones nuevas: `EN_PROGRESO → EN_ESPERA` (exige motivo) y `EN_ESPERA → EN_PROGRESO | CERRADO`. Los filtros de estado del área y del panel admin incluyen el estado nuevo, y la celda de acciones de la cola del área ahora se decide por estado y no por número de transiciones.
- `GestorSLA`: métodos nuevos `pausar_reloj`, `reanudar_reloj` y `segundos_en_pausa`; `consumo_sla` descuenta las pausas, de modo que el porcentaje se congela mientras el ticket espera.
- Columnas nuevas: `tickets.sla_pausado_desde`, `tickets.sla_segundos_pausados` y `tickets.requiere_cobertura`; tablas nuevas `webhooks` y `entregas_webhook`. Las añade `python init_db.py` sin pérdida de datos.
- Acciones de auditoría nuevas: `pausar_sla`, `reanudar_sla`, `tomar_cobertura`, `crear_webhook`, `editar_webhook`, `eliminar_webhook` y `probar_webhook`.
- Servicios nuevos: `app/services/webhooks.py` y `app/services/busqueda.py`. Métodos nuevos en `ServicioTickets`: `reanudar_por_respuesta`, `listar_pendientes_cobertura` y `tomar_cobertura`.
- Variables de entorno nuevas: `WEBHOOKS_EN_HILO` (por defecto 1) y `WEBHOOKS_PERMITIR_DESTINOS_LOCALES` (por defecto 0).
- 66 pruebas nuevas (`tests/test_espera_sla.py`, `tests/test_cobertura.py`, `tests/test_webhooks.py`, `tests/test_busqueda.py`): 385 en total.
- Se regeneró `messages.pot` y se completaron las 104 cadenas nuevas en inglés, que era el pendiente de la 3.1.

### Pendiente
- Los webhooks se entregan en un hilo con un máximo de 3 intentos seguidos; no hay cola persistente, así que un destino caído durante toda la ventana de reintentos pierde ese evento (queda registrado en la bitácora como fallo).
- La pausa de SLA no tiene tope: un ticket puede quedarse en espera indefinidamente si el solicitante nunca responde. Un cierre automático por falta de respuesta sería la continuación natural.

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
- ~~`messages.pot` no se regeneró: las 64 cadenas nuevas se anexaron traducidas a `app/translations/en/LC_MESSAGES/messages.po`.~~ Resuelto en 3.5.0.
- ~~El caso de un ticket **ya asignado** a un agente que después se marca ausente sigue avisando solo a ese agente.~~ Resuelto en 3.5.0 (cobertura de ausencias).

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
