# Lógica del proyecto

## Flujo principal del sistema

1. Un **usuario final** crea un ticket describiendo su problema en texto libre.
2. El **algoritmo de clasificación** analiza el texto y determina:
   - La **categoría/área de soporte** correspondiente.
   - Una **prioridad base**, según la categoría y palabras de urgencia detectadas en el texto.
3. Si el usuario que reportó el ticket tiene **nivel VIP**, la prioridad se eleva a atención inmediata, independientemente de la categoría.
4. El sistema calcula la **fecha límite de atención (SLA)** a partir de la prioridad final.
5. El ticket queda visible para los **agentes del área** correspondiente, ordenado por prioridad.
6. Un agente toma el ticket, cambia su estado, agrega comentarios y lo resuelve.
7. Si el ticket se acerca a su fecha límite sin resolverse, el sistema genera un **recordatorio** visible tanto para quien lo creó como para el agente asignado.
8. Cada acceso y acción crítica (creación de ticket, cambio de estado, inicio de sesión) queda registrada en el **log de auditoría**.
9. El **administrador** puede consultar el log de auditoría completo y un panel de métricas del sistema.

## Algoritmo de clasificación

El sistema clasifica cada ticket en una de las siguientes categorías, que corresponden directamente a un área de soporte:

- **Infraestructura** (hardware)
- **Redes**
- **Permisos**
- **Cuentas y contraseñas**
- **Hackeos/Seguridad**
- **Software/Aplicaciones**
- **Otros/General** (categoría por defecto cuando no hay coincidencia clara)

La clasificación se realiza por coincidencia de palabras clave características de cada categoría en el texto del ticket. Cuando varias categorías comparten palabras (por ejemplo, "acceso" aparece tanto en Permisos como en Cuentas y contraseñas), se aplican reglas de desempate explícitas para evitar ambigüedad.

## Cálculo de prioridad

La prioridad final de un ticket se determina en dos pasos:

1. **Prioridad base**, calculada según la categoría y la presencia de palabras que indican urgencia o impacto (por ejemplo, "no puedo trabajar", "se cayó todo").
2. **Ajuste por nivel del solicitante**: si el usuario es VIP/ejecutivo, la prioridad se eleva automáticamente a atención inmediata, sin importar el resultado del paso anterior.

## Autenticación y seguridad

- Las contraseñas nunca se almacenan en texto plano: se guarda únicamente su hash (bcrypt).
- El sistema lleva el conteo de intentos fallidos de inicio de sesión por usuario; al superar un número configurable de intentos, la cuenta queda bloqueada temporalmente.
- Todo acceso y toda acción crítica quedan registrados en el log de auditoría, que no es editable ni eliminable desde la interfaz de la aplicación.
