# Lógica del proyecto

## Flujo principal del sistema

1. Un **usuario final** crea un ticket describiendo su problema en texto libre.
2. El **algoritmo de clasificación** analiza el texto y determina la **categoría/área de
   soporte** correspondiente, buscando coincidencias de palabras clave.
3. Según la categoría, el sistema le asigna una **prioridad base** fija (ver tabla abajo).
4. Si el usuario que reportó el ticket tiene **nivel VIP**, la prioridad final se eleva
   siempre a **ALTA**, sin importar la prioridad base de la categoría.
5. El sistema calcula la **fecha límite de atención (SLA)** a partir de la prioridad final
   **y del nivel del usuario** (los usuarios VIP tienen una tabla de horas de SLA distinta y
   más corta, no solo una prioridad más alta).
6. El ticket queda visible para los **agentes del área** correspondiente, ordenado por
   prioridad. No se asigna ningún agente automáticamente al crearlo.
7. Un agente toma el ticket (lo pasa a `EN_PROGRESO` indicando su propio `agente_id`), cambia
   su estado, agrega comentarios y finalmente lo cierra.
8. Si un ticket está vencido o próximo a vencer, la vista de tickets por área (`/tickets/area/<area>`)
   lo resalta en rojo o amarillo para los **agentes**.
9. Cada acceso y acción crítica (creación de ticket, cambio de estado, reasignación,
   comentario, login exitoso/fallido, bloqueo/desbloqueo de cuenta, registro de usuario) queda
   registrada en el **log de auditoría**.
10. El administrador puede consultar el log de auditoría completo y un panel de métricas del sistema.

## Algoritmo de clasificación
El sistema clasifica cada ticket en una de las siguientes categorías, que corresponden
directamente a un área de soporte:

- **Seguridad**
- **Redes**
- **Infraestructura** (hardware)
- **Permisos**
- **Cuentas y contraseñas**
- **Software/Aplicaciones**
- **Otros/General** (categoría por defecto cuando no hay coincidencia clara)

La clasificación se realiza por coincidencia de palabras clave características de cada
categoría en el texto del ticket (todas centralizadas en el diccionario `PALABRAS_CLAVE` de
`ClasificadorTickets`). Cuando varias categorías comparten palabras (por
ejemplo, "no puedo entrar a" en Permisos vs. "contraseña" en Cuentas y contraseñas), el
desempate **no es una regla explícita aparte**: se resuelve por el **orden en que aparecen las
categorías dentro del diccionario** — la primera categoría del diccionario cuyas palabras
coincidan con el texto es la que gana. Con el orden actual (Seguridad, Redes,
Infraestructura, Permisos, Cuentas y contraseñas, Software), Permisos siempre gana sobre
Cuentas y contraseñas en caso de ambigüedad, que es el caso que cubren las pruebas en
`tests/test_clasificador.py`.

## Cálculo de prioridad

La prioridad final de un ticket se determina en dos pasos:

1. **Prioridad base**, asignada de forma fija según la categoría (tabla
   `PRIORIDAD_BASE_POR_CATEGORIA` en `ServicioTickets`): Seguridad y Redes → Alta;
   Infraestructura → Media; Permisos, Cuentas y contraseñas, Software y Otros → Baja.
   *(A diferencia de versiones anteriores de este documento, la prioridad base **no** analiza
   palabras de urgencia en el texto — depende únicamente de la categoría detectada.)*
2. **Ajuste por nivel del solicitante**: si el usuario es VIP, la prioridad final se eleva
   automáticamente a **Alta**, sin importar el resultado del paso anterior.

## Cálculo del SLA

El plazo límite no depende solo de la prioridad final, sino también del nivel del usuario:

| Prioridad | Horas SLA (usuario normal) | Horas SLA (usuario VIP) |
|---|---|---|
| Alta | 4 | 1.5 |
| Media | 24 | 4.5 |
| Baja | 72 | 10.5 |

Un ticket se marca como **próximo a vencer** cuando le queda un 20% o menos del tiempo total
entre su creación y su fecha límite, y como **vencido** cuando ya pasó la fecha límite y sigue
sin cerrarse.

## Autenticación y seguridad

- Las contraseñas nunca se almacenan en texto plano: se guarda únicamente su hash (bcrypt),
  generado y verificado exclusivamente por `ServicioAutenticacion`.
- El sistema lleva el conteo de intentos fallidos de inicio de sesión por usuario; al llegar a
  **3 intentos fallidos**, la cuenta queda bloqueada durante **5 horas**. Al vencer ese
  período, el primer intento de login siguiente desbloquea la cuenta y reinicia el contador.
- Todo acceso y toda acción crítica quedan registrados en el log de auditoría, que no es
  editable ni eliminable desde la interfaz de la aplicación — aunque, como se indicó arriba,
  tampoco es **consultable** desde la interfaz todavía.
