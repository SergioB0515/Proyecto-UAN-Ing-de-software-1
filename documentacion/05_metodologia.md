# Modelo de desarrollo

## Metodología

El proyecto se desarrolla bajo el marco de trabajo **Scrum**, con sprints de 2 semanas.

## Roles

| Rol | Asignación | Responsabilidad |
|---|---|---|
| Product Owner | Definido junto al docente | Prioriza el backlog y valida los criterios de aceptación de cada historia. |
| Scrum Master | Desarrollador principal | Facilita las ceremonias, elimina bloqueos y da seguimiento al avance del sprint. |
| Dev Team | Los tres integrantes del equipo | Ejecuta las tareas del sprint backlog. |

## Artefactos

- **Product Backlog:** lista priorizada de historias de usuario (ver `06_historias_usuario.md`).
- **Sprint Backlog:** subconjunto de historias comprometidas para cada sprint.
- **Incremento:** versión funcional del sistema al cierre de cada sprint.

## Ceremonias

| Ceremonia | Frecuencia | Propósito |
|---|---|---|
| Sprint Planning | Inicio de cada sprint | Seleccionar y estimar las historias del sprint backlog. |
| Daily Standup | Diaria (asíncrona, por chat de equipo) | Reportar avance, plan del día y bloqueos. |
| Sprint Review | Cierre de cada sprint | Demostrar el incremento funcional al equipo y, si aplica, al docente. |
| Sprint Retrospective | Cierre de cada sprint | Identificar qué mejorar en el proceso de trabajo, incluyendo el cumplimiento de tareas asignadas. |

## Definition of Ready (DoR)

Una historia de usuario está lista para entrar a un sprint cuando:
- Tiene criterios de aceptación claros y verificables.
- Su tamaño permite completarla dentro de un único sprint.
- No depende de una historia que aún no se ha completado.

## Definition of Done (DoD)

Una historia de usuario se considera terminada cuando:
- El código está implementado, integrado a la rama principal y libre de errores conocidos.
- Fue probada manualmente contra sus criterios de aceptación.
- Cuenta con comentarios claros en el código.
- La documentación relacionada fue actualizada si hubo cambios.

## Plan de sprints

| Sprint | Duración | Entregable principal (desarrollador principal) |
|---|---|---|
| Sprint 1 | 2 semanas | Modelo de base de datos, autenticación con roles y CRUD base de tickets. |
| Sprint 2 | 2 semanas | Algoritmo de clasificación, ajuste de prioridad por nivel VIP, cálculo de SLA y recordatorios. |
| Sprint 3 | 2 semanas | Módulo de auditoría, bloqueo por fuerza bruta y panel de métricas. |
| Sprint 4 | 2 semanas | Integración final, corrección de errores y documentación. |

## Reglas de trabajo en equipo

- Toda tarea asignada a un integrante queda registrada por escrito en el tablero del equipo, con responsable y fecha límite visibles.
- Todos los integrantes registran su trabajo mediante commits propios en el repositorio compartido; el historial de Git es la evidencia objetiva de aporte individual.
- Ninguna tarea de la ruta crítica del proyecto depende de un integrante distinto al desarrollador principal, para evitar bloqueos por incumplimiento.
- El incumplimiento de una tarea asignada se documenta en la retrospectiva del sprint correspondiente.
