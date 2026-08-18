# Historias de usuario

1. Como usuario final, quiero crear un ticket describiendo mi problema, para que sea atendido por el equipo de soporte.
2. Como sistema, quiero clasificar y enrutar automáticamente cada ticket por categoría y área, para reducir errores de enrutamiento manual.
3. Como sistema, quiero elevar la prioridad de un ticket cuando el solicitante es VIP/ejecutivo, para reflejar la urgencia real del negocio.
4. Como sistema, quiero calcular un plazo de atención y avisar cuando esté por vencer, para que ningún ticket se quede sin respuesta.
5. Como agente, quiero ver los tickets de mi área ordenados por prioridad, para atender primero los casos más urgentes.
6. Como administrador, quiero ver un registro de quién accedió o modificó cada ticket y cuándo, para poder auditar el uso del sistema.
7. Como administrador, quiero que el sistema bloquee cuentas tras varios intentos fallidos de inicio de sesión, para mitigar ataques de fuerza bruta.

## Casos de uso principales

| ID | Actor | Descripción |
|---|---|---|
| CU-01 | Usuario final | Crear un nuevo ticket describiendo una incidencia. |
| CU-02 | Sistema | Clasificar, enrutar y priorizar automáticamente el ticket recién creado. |
| CU-03 | Sistema | Calcular el SLA y emitir recordatorios de vencimiento. |
| CU-04 | Agente | Consultar los tickets de su área, ordenados por prioridad. |
| CU-05 | Agente | Actualizar el estado de un ticket y agregar comentarios. |
| CU-06 | Administrador | Consultar el registro de auditoría de accesos y acciones. |
| CU-07 | Administrador | Consultar el panel de métricas del sistema. |
