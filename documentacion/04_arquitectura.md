# Avances de arquitectura

## Stack tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Backend | Python + Flask | Framework simple, sin sobre-ingeniería, adecuado para el tamaño del equipo y el tiempo disponible. |
| Base de datos | SQLite | Cero configuración de servidor, suficiente para el volumen de datos del proyecto. |
| ORM | SQLAlchemy (Flask-SQLAlchemy) | Evita escribir SQL a mano para las operaciones básicas y mantiene el modelo de datos como código Python. |
| Frontend | HTML/CSS + plantillas Jinja2 | Sin framework de frontend adicional, evitando complejidad innecesaria. |
| Control de versiones | Git + GitHub | Historial de commits como evidencia de aporte individual de cada integrante del equipo. |

## Modelo de datos

| Entidad | Campos principales |
|---|---|
| **Usuario** | id, nombre, email, contraseña_hash, rol (final/agente/admin), área_soporte (si es agente), nivel (normal/VIP), intentos_fallidos, bloqueado_hasta |
| **Ticket** | id, radicado, texto, categoría, prioridad, estado, creador_id, agente_id, fecha_creación, fecha_límite |
| **Comentario** | id, ticket_id, autor_id, texto, fecha |
| **LogAuditoria** | id, usuario_id, acción, detalle, fecha |

## Separación de responsabilidades

Siguiendo el principio de responsabilidad única, la lógica de negocio se separa de las entidades de datos en clases de servicio independientes:

| Clase de servicio | Responsabilidad |
|---|---|
| `ServicioAutenticacion` | Registro de usuarios, verificación de credenciales, generación de hash de contraseña y control de bloqueo por intentos fallidos. Única clase autorizada a manejar contraseñas en texto plano. |
| `ClasificadorTickets` | Determina categoría, área de soporte y prioridad base de un ticket a partir de su texto. |
| `GestorSLA` | Calcula la fecha límite de atención según la prioridad final y verifica qué tickets están próximos a vencer. |

## Diagrama de clases

```mermaid
classDiagram
  class Usuario {
    +int id
    +string nombre
    +string email
    -string contrasena_hash
    +RolUsuario rol
    +Categoria area_soporte
    +NivelUsuario nivel
    +int intentos_fallidos
    +datetime bloqueado_hasta
  }
  class Ticket {
    +int id
    +string radicado
    +string texto
    +Categoria categoria
    +Prioridad prioridad
    +EstadoTicket estado
    +int creador_id
    +int agente_id
    +datetime fecha_creacion
    +datetime fecha_limite
  }
  class Comentario {
    +int id
    +int ticket_id
    +int autor_id
    +string texto
    +datetime fecha
  }
  class LogAuditoria {
    +int id
    +int usuario_id
    +string accion
    +string detalle
    +datetime fecha
  }
  class ClasificadorTickets {
    +clasificar(texto) Categoria
    +calcularPrioridad(categoria, nivel) Prioridad
  }
  class GestorSLA {
    +calcularFechaLimite(prioridad) datetime
    +verificarVencimientos()
  }
  class ServicioAutenticacion {
    +registrar(nombre, email, contrasena) Usuario
    +iniciarSesion(email, contrasena) bool
    -verificarContrasena(plano, hash) bool
    -generarHash(plano) string
    +estaBloqueado(usuario) bool
  }
  Usuario "1" --> "0..*" Ticket : crea
  Usuario "1" --> "0..*" Ticket : atiende
  Ticket "1" --> "0..*" Comentario : tiene
  Usuario "1" --> "0..*" Comentario : autor
  Usuario "1" --> "0..*" LogAuditoria : genera
  ClasificadorTickets ..> Ticket : clasifica
  GestorSLA ..> Ticket : calcula SLA
  ServicioAutenticacion ..> Usuario : autentica
  ServicioAutenticacion ..> LogAuditoria : registra intentos
```

*(Este bloque se renderiza automáticamente como diagrama al verlo en GitHub.)*

## Estado actual de la implementación

- [x] Modelos de datos (`Usuario`, `Ticket`, `Comentario`, `LogAuditoria`) implementados y verificados contra la base de datos real.
- [x] `create_app()` y conexión de la base de datos funcionando.
- [x] `ServicioAutenticacion`: generación y verificación de hash de contraseña (bcrypt).
- [ ] `ServicioAutenticacion`: registro completo de usuarios y control de bloqueo por intentos fallidos.
- [ ] `ClasificadorTickets`.
- [ ] `GestorSLA`.
- [ ] Log de auditoría integrado al flujo de la aplicación.
- [ ] Interfaz web (plantillas HTML).
