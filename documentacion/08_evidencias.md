# Evidencias de funcionamiento

*Esta sección se completa con capturas de pantalla o grabaciones cortas a medida que cada
funcionalidad queda lista y probada. Guarda las imágenes en `documentacion/img/` y enlázalas
aquí con `![descripción](img/nombre.png)`.*

*(Actualizado: la mayoría de las funcionalidades de Sprint 1-3 ya están implementadas — ver
`07_avances.md` — así que las capturas pendientes abajo ya se pueden tomar. Las dos marcadas
como "no aplica" corresponden a funcionalidades que todavía no existen en la interfaz.)*

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

- [ ] **No aplica todavía:** captura del log de auditoría mostrando accesos y acciones registradas — pendiente hasta que exista una pantalla para consultarlo (ver `04_arquitectura.md`, punto pendiente).
- [ ] Captura del panel de métricas (`/dashboard`) para el administrador.

## Sprint 4

- [ ] **No aplica todavía:** captura de un recordatorio de SLA visible para el creador del ticket — pendiente de implementación (ver `03_logica.md`).
- [ ] Grabación corta (GIF o video) del flujo completo: creación de ticket → clasificación → atención por un agente → cierre.
