# Historias de usuario

1. Como usuario final, quiero crear un ticket describiendo mi problema, para que sea atendido por el equipo de soporte.
2. Como sistema, quiero clasificar y enrutar automáticamente cada ticket por categoría y área, para reducir errores de enrutamiento manual.
3. Como sistema, quiero elevar la prioridad de un ticket cuando el solicitante es VIP/ejecutivo, para reflejar la urgencia real del negocio.
4. Como sistema, quiero calcular un plazo de atención y avisar cuando esté por vencer, para que ningún ticket se quede sin respuesta.
5. Como agente, quiero ver los tickets de mi área ordenados por prioridad, para atender primero los casos más urgentes.
6. Como administrador, quiero ver un registro de quién accedió o modificó cada ticket y cuándo, para poder auditar el uso del sistema.
7. Como administrador, quiero que el sistema bloquee cuentas tras varios intentos fallidos de inicio de sesión, para mitigar ataques de fuerza bruta. **(el umbral se ajustó a 3 intentos por indicación del profesor; antes era 5)**
8. Como usuario final o agente, quiero ver un recordatorio visual cuando mis propios tickets estén vencidos o próximos a vencer, no solo el agente que los atiende.
9. Como cualquier usuario autenticado, quiero poder cambiar mi propia contraseña y mi nombre desde un perfil, sin depender del administrador.
10. Como agente, quiero ver mis propias estadísticas de desempeño (tickets tomados y cerrados) en mi perfil.
11. Como agente o administrador, quiero filtrar la lista de tickets de mi área por estado, prioridad y rango de fechas, para encontrar casos específicos más rápido.
12. Como administrador, quiero que el sistema detecte y bloquee temporalmente direcciones IP con patrones de intentos de acceso sospechosos (varios usuarios distintos fallando desde la misma IP), sin penalizar redes compartidas legítimas (ej. una oficina) por errores normales de un solo usuario.
13. Como administrador, quiero poder hacer clic en cualquier número del panel de métricas y ver la lista real de tickets que lo componen (drill-down), en vez de solo ver el agregado.
14. Como administrador, quiero exportar la lista de tickets, el resumen de métricas y el log de auditoría a CSV o Excel, para analizarlos fuera del sistema.
15. Como cualquier usuario, quiero proteger mi cuenta con verificación en dos pasos y poder recuperar mi contraseña por correo sin depender del administrador.
16. Como usuario final, quiero que mientras describo mi problema el sistema me sugiera guías que puedan resolverlo, para no tener que esperar a soporte.
17. Como agente, quiero escribir artículos de ayuda y compartirlos en mis respuestas, para no repetir las mismas explicaciones.
18. Como usuario final o agente, quiero adjuntar capturas y archivos a un ticket, para mostrar el error exacto.
19. Como agente, quiero dejar notas internas que el usuario no vea y usar respuestas rápidas, para coordinarme con el equipo y responder más rápido.
20. Como agente o administrador, quiero seguir tickets que no tengo asignados, para enterarme de su actividad.
21. Como usuario final, quiero calificar la atención recibida al cerrarse mi ticket.
22. Como administrador, quiero ver tendencias, tiempos de respuesta y resolución, cumplimiento de SLA por categoría, rendimiento de agentes y satisfacción, comparados con el periodo anterior.
23. Como administrador, quiero gestionar las cuentas (rol, área, nivel, activación, desbloqueo, recuperación, verificación en dos pasos) desde una sola pantalla.
24. Como usuario, quiero integrar el sistema con mis scripts mediante una API con tokens personales que pueda revocar.
25. Como usuario final, quiero que nadie fuera de mi ticket (salvo el personal autorizado) pueda leerlo.

## Casos de uso principales

| ID | Actor | Descripción | Estado |
|---|---|---|---|
| CU-01 | Usuario final | Crear un nuevo ticket describiendo una incidencia. | Implementado |
| CU-02 | Sistema | Clasificar, enrutar y priorizar automáticamente el ticket recién creado. | Implementado |
| CU-03 | Sistema | Calcular el SLA y emitir recordatorios de vencimiento, visibles tanto para el agente como para el creador del ticket. | Implementado |
| CU-04 | Agente | Consultar los tickets de su área, ordenados por prioridad, con filtros por estado/prioridad/fecha. | Implementado |
| CU-05 | Agente | Actualizar el estado de un ticket y agregar comentarios. | Implementado |
| CU-06 | Administrador | Consultar el registro de auditoría de accesos y acciones, con filtros y paginación. | Implementado |
| CU-07 | Administrador | Consultar el panel de métricas del sistema, con drill-down a la lista de tickets detrás de cada número. | Implementado |
| CU-08 | Cualquier usuario autenticado | Gestionar su propio perfil: cambiar contraseña, cambiar nombre, subir foto de perfil, ver sus estadísticas. | Implementado |
| CU-09 | Administrador | Consultar y filtrar el listado global de tickets del sistema (no solo por área), con exportación a CSV/Excel. | Implementado |
| CU-10 | Sistema | Bloquear temporalmente una IP tras detectar intentos fallidos de login contra varios usuarios distintos en una ventana corta de tiempo. | Implementado |
| CU-11 | Cualquier usuario autenticado | Activar la verificación en dos pasos y recuperar la contraseña mediante un enlace de un solo uso. | Implementado |
| CU-12 | Usuario final | Consultar la base de conocimiento y recibir sugerencias de artículos al crear un ticket. | Implementado |
| CU-13 | Agente / Administrador | Crear, editar, publicar y archivar artículos de la base de conocimiento. | Implementado |
| CU-14 | Usuario final / Agente | Adjuntar archivos, comentar y (personal) agregar notas internas, usar respuestas rápidas y seguir tickets. | Implementado |
| CU-15 | Usuario final | Calificar la atención de un ticket cerrado. | Implementado |
| CU-16 | Administrador | Consultar la analítica del servicio y exportarla a CSV. | Implementado |
| CU-17 | Administrador | Gestionar las cuentas de usuario. | Implementado |
| CU-18 | Cualquier usuario autenticado | Crear y revocar tokens personales y consumir la API REST. | Implementado |
