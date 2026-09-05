# Evidencias de funcionamiento

*Esta sección se completa con capturas de pantalla o grabaciones cortas a medida que cada
funcionalidad queda lista y probada. Guarda las imágenes en `documentacion/img/` y enlázalas
aquí con `![descripción](img/nombre.png)`.*

*(Actualizado al cierre de la 1.6: todas las funcionalidades del proyecto ya están
implementadas — ver `07_avances.md` — así que todas las capturas de este documento ya se
pueden tomar. No quedan casos marcados como "no aplica".)*

## Sprint 1

### Modelos de base de datos
- [ ] Captura del visor de SQLite mostrando las 4 tablas creadas (`usuarios`, `tickets`, `comentarios`, `log_auditoria`) con sus columnas.

### Autenticación
- [ ] Captura de terminal mostrando la generación de un hash de contraseña y su verificación exitosa/fallida.
- [ ] Captura del registro de un usuario nuevo mostrando el registro guardado en la base de datos con la contraseña ya hasheada, no en texto plano.
- [ ] Captura de un intento de inicio de sesión fallido repetido (3 intentos), mostrando el bloqueo de la cuenta.

## Sprint 2

- [ ] Captura de un ticket recién creado mostrando la categoría, área y prioridad asignadas automáticamente por el algoritmo.
- [ ] Captura de un ticket creado por un usuario VIP mostrando la prioridad elevada a Alta.
- [ ] Captura del cálculo de fecha límite (SLA), comparando un ticket normal y uno VIP de la misma prioridad.
- [ ] Captura de la vista `/tickets/area/<area>` mostrando tickets ordenados por prioridad, con vencidos/próximos a vencer resaltados.

## Sprint 3

- [ ] Captura del log de auditoría (`/auditoria`) mostrando accesos y acciones registradas, con al menos un filtro aplicado.
- [ ] Captura del panel de métricas (`/metricas`) para el administrador.

## Sprint 4

- [ ] Captura del dashboard del usuario final mostrando un ticket propio resaltado como vencido o próximo a vencer.
- [ ] Grabación corta (GIF o video) del flujo completo: creación de ticket → clasificación → atención por un agente → cierre.

## Versión 1.1

- [ ] Captura del log de auditoría filtrado por usuario y por acción, mostrando la paginación.
- [ ] Captura del dashboard del creador mostrando el mismo highlighting de vencidos/próximos a vencer que ya existía para el agente.

## Versión 1.2

- [ ] Captura del formulario de cambio de contraseña, incluyendo un intento fallido (contraseña actual incorrecta) mostrando el mensaje de error.
- [ ] Captura de `listar_por_area` con los 3 filtros (estado, prioridad, fecha) aplicados a la vez.

## Versión 1.3

- [ ] Captura de un intento de registro/cambio de contraseña rechazado por no cumplir la política (falta mayúscula, número o símbolo).
- [ ] Captura de un login rechazado por bloqueo de IP, junto con el log de auditoría o la tabla `IPBloqueada` mostrando el registro correspondiente.
- [ ] Captura de la terminal mostrando el mensaje de limpieza automática del `APScheduler`.

## Versión 1.4

- [ ] Captura del perfil de un agente mostrando sus estadísticas (tickets tomados/cerrados), la foto de perfil subida, y el nombre editado.
- [ ] Captura del panel de métricas con un clic en un número llevando al listado de tickets filtrado (drill-down).
- [ ] Captura de un archivo Excel exportado (tickets, métricas o auditoría) abierto, mostrando los datos correctos.

## Versión 1.5

- [ ] Captura de "antes/después" del rediseño visual (una pantalla representativa, ej. login o dashboard).

## Versión 1.6

- [ ] Captura de la terminal corriendo `pytest -v` con todos los tests en verde.
- [ ] Captura de la pestaña Actions en GitHub mostrando una corrida exitosa (check verde) del workflow de CI.
