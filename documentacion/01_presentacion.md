# Presentación del proyecto

## Descripción general

Sistema de gestión de incidencias (tickets) para el área de soporte de TI de una empresa. Permite a cualquier empleado reportar un problema en texto libre; el sistema lo clasifica automáticamente, lo enruta al área de soporte correspondiente, le asigna una prioridad, y da seguimiento a su resolución mediante plazos de atención (SLA) y un registro de auditoría de seguridad.

## Objetivo general

Desarrollar una plataforma de gestión de incidencias que clasifique y enrute automáticamente los tickets, gestione plazos de atención según prioridad y nivel del solicitante, e incorpore un módulo de auditoría de seguridad sobre los accesos al sistema.

## Objetivos específicos

1. Implementar autenticación y autorización con roles diferenciados (administrador, agente, usuario final).
2. Implementar el ciclo de vida completo de un ticket (creación, asignación, cambio de estado, comentarios, cierre).
3. Diseñar e implementar un algoritmo que clasifique cada ticket por categoría, lo enrute al área de soporte correspondiente y le asigne una prioridad base.
4. Ajustar la prioridad final del ticket considerando el nivel del solicitante (usuario VIP/ejecutivo vs. usuario normal).
5. Calcular un plazo límite de atención (SLA) según la prioridad final y notificar mediante recordatorios cuando un ticket esté próximo a vencer.
6. Registrar de forma inmutable los accesos y acciones críticas ejecutadas sobre el sistema.
7. Detectar y mitigar intentos de acceso no autorizado mediante bloqueo por intentos fallidos repetidos.
8. Medir y presentar métricas de desempeño del sistema mediante un panel para el administrador.

## Alcance

### Incluido en el proyecto (MVP)
- Autenticación de usuarios con roles y almacenamiento seguro de contraseñas.
- Gestión de tickets: creación, asignación, cambio de estado y comentarios.
- Algoritmo de clasificación que asigna categoría, área de soporte y prioridad base a cada ticket.
- Ajuste de prioridad por nivel del solicitante (VIP vs. normal).

### Extensiones (según disponibilidad de tiempo)
- Cálculo de SLA y recordatorios automáticos de vencimiento.
- Módulo de auditoría: registro inmutable de accesos y acciones críticas.
- Bloqueo por intentos de inicio de sesión fallidos repetidos.
- Panel de métricas para el administrador.

### Fuera de alcance
- Despliegue en infraestructura de producción o en la nube.
- Integración con sistemas de terceros (correo electrónico, mensajería, etc.).
- Modelado detallado de la estructura organizacional completa de la empresa; solo se distingue el nivel del solicitante (normal/VIP) en la medida en que afecta la prioridad.
