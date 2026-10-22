# Changelog

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
