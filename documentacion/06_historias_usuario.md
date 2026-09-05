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
