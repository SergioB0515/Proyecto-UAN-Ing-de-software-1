import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.articulo import Articulo
from app.models.comentario import Comentario
from app.models.encuesta_satisfaccion import EncuestaSatisfaccion
from app.models.enum import Categoria, EstadoTicket, RolUsuario
from app.models.respuesta_predefinida import RespuestaPredefinida
from app.models.ticket import Ticket
from app.models.usuario import Usuario

ARTICULOS = [
    {
        "titulo": "Cómo restablecer tu contraseña",
        "categoria": Categoria.CUENTAS_CONTRASENAS,
        "etiquetas": "contraseña, olvidé, recuperar, acceso, login",
        "resumen": "Recupera el acceso a tu cuenta en menos de dos minutos con el enlace de recuperación.",
        "contenido": """Si olvidaste tu contraseña o tu cuenta quedó bloqueada, puedes recuperarla tú mismo sin abrir un ticket.

## Pasos
1. En la pantalla de inicio de sesión pulsa **¿Olvidaste tu contraseña?**
2. Escribe el correo corporativo con el que te registraron.
3. Abre el enlace que te llega por correo. Es válido durante **30 minutos** y solo funciona una vez.
4. Elige una contraseña nueva que cumpla la política: mínimo 8 caracteres, con mayúscula, minúscula, número y símbolo.

> Al restablecer la contraseña tu cuenta se desbloquea automáticamente.

## ¿No te llega el correo?
- Revisa la carpeta de spam o correo no deseado.
- Espera un par de minutos: por seguridad solo se permiten 3 solicitudes por hora.
- Si aun así no llega, crea un ticket en la categoría *Cuentas y contraseñas*.""",
    },
    {
        "titulo": "Activar la verificación en dos pasos",
        "categoria": Categoria.SEGURIDAD,
        "etiquetas": "2fa, seguridad, autenticador, códigos, verificación",
        "resumen": "Protege tu cuenta con una app de autenticación y guarda tus códigos de respaldo.",
        "contenido": """La verificación en dos pasos añade un código temporal de 6 dígitos a tu inicio de sesión.

## Configuración
1. Ve a **Mi perfil → Verificación en dos pasos** y pulsa *Activar*.
2. Escanea el código QR con Google Authenticator, Microsoft Authenticator, Authy o similar.
3. Escribe el código de 6 dígitos que muestra la app para confirmar.
4. **Descarga o imprime tus 8 códigos de respaldo** y guárdalos en un lugar seguro.

## Si pierdes el teléfono
Usa uno de tus códigos de respaldo (cada uno sirve una sola vez). Si tampoco los tienes, un administrador puede restablecer tu verificación desde la gestión de usuarios.""",
    },
    {
        "titulo": "Conectarte a la VPN desde casa",
        "categoria": Categoria.REDES,
        "etiquetas": "vpn, remoto, teletrabajo, conexión, casa",
        "resumen": "Configura el cliente VPN corporativo y soluciona los cortes más frecuentes.",
        "contenido": """Necesitas la VPN para acceder a carpetas compartidas y aplicaciones internas fuera de la oficina.

## Primera conexión
1. Instala el cliente VPN desde el portal de software de la empresa.
2. Usa como servidor `vpn.empresa.com` y tu usuario corporativo.
3. Acepta la notificación de verificación en tu teléfono si se solicita.

## La VPN se desconecta cada pocos minutos
- Conéctate por cable o acércate al router: la VPN es sensible a la pérdida de paquetes.
- Desactiva el ahorro de energía del adaptador de red.
- Cierra otras VPN o proxys personales.
- Reinicia el cliente y vuelve a intentarlo.

Si el problema continúa, adjunta al ticket una captura del mensaje de error y el resultado de `ping vpn.empresa.com`.""",
    },
    {
        "titulo": "No tengo internet en mi equipo",
        "categoria": Categoria.REDES,
        "etiquetas": "internet, wifi, red, sin conexión, lento",
        "resumen": "Comprobaciones rápidas antes de reportar una caída de red.",
        "contenido": """Antes de crear un ticket revisa si el problema es solo tuyo o de toda el área.

## Comprobaciones
1. ¿Tus compañeros tienen conexión? Si nadie la tiene, es una caída general: el equipo de redes ya está avisado por el monitoreo.
2. Desconecta y vuelve a conectar el WiFi o el cable de red.
3. Reinicia el equipo.
4. Prueba a abrir varias páginas distintas para descartar que sea un solo sitio.

## Internet muy lento
- Cierra descargas o sincronizaciones grandes (OneDrive, actualizaciones).
- Si estás por WiFi, acércate al punto de acceso.

Indica en el ticket tu ubicación (piso y puesto) para agilizar la revisión.""",
    },
    {
        "titulo": "Solicitar acceso a una carpeta compartida",
        "categoria": Categoria.PERMISOS,
        "etiquetas": "permisos, carpeta, acceso denegado, compartida, unidad",
        "resumen": "Qué información incluir para que tu solicitud de permisos se apruebe a la primera.",
        "contenido": """Los permisos sobre carpetas compartidas los aprueba el responsable de cada área.

## Incluye en tu ticket
- La **ruta completa** de la carpeta (por ejemplo `\\\\servidor\\finanzas\\2026`).
- El **tipo de acceso**: solo lectura o lectura y escritura.
- El **nombre de tu jefe directo**, que debe aprobar la solicitud.
- Desde cuándo y hasta cuándo lo necesitas, si es temporal.

> Si antes tenías acceso y ahora ves *Acceso denegado*, indícalo: suele deberse a un cambio de grupo y se resuelve más rápido.""",
    },
    {
        "titulo": "La impresora no imprime",
        "categoria": Categoria.INFRAESTRUCTURA,
        "etiquetas": "impresora, imprimir, cola, papel, atasco",
        "resumen": "Soluciona los atascos de cola y errores de impresión más comunes.",
        "contenido": """## Revisa primero
1. Que la impresora esté encendida y sin mensajes de error en su pantalla (papel, tóner, atasco).
2. Que hayas elegido la impresora correcta: los nombres incluyen el piso, por ejemplo `IMP-P3-COLOR`.

## Vaciar la cola de impresión
1. Abre **Configuración → Bluetooth y dispositivos → Impresoras**.
2. Selecciona la impresora y pulsa *Abrir cola de impresión*.
3. Cancela todos los documentos y vuelve a imprimir.

Si otras personas tampoco pueden imprimir en esa impresora, indícalo en el ticket: se tratará como incidencia del equipo y no de tu ordenador.""",
    },
    {
        "titulo": "El equipo no enciende o se apaga solo",
        "categoria": Categoria.INFRAESTRUCTURA,
        "etiquetas": "no enciende, se apaga, batería, hardware, pantalla azul",
        "resumen": "Pasos básicos de diagnóstico de hardware antes de solicitar una revisión.",
        "contenido": """## Si no enciende
- Comprueba el cable de corriente y prueba otro enchufe.
- En portátiles, conecta el cargador y espera 10 minutos antes de volver a intentarlo.
- Mantén pulsado el botón de encendido 15 segundos y suéltalo.

## Si se apaga solo o muestra pantalla azul
- Anota el **código de error** que aparece (por ejemplo `MEMORY_MANAGEMENT`).
- Revisa que las rejillas de ventilación no estén obstruidas.
- Guarda tu trabajo con frecuencia hasta que el equipo sea revisado.

Adjunta una foto de la pantalla de error al ticket: ayuda mucho al diagnóstico.""",
    },
    {
        "titulo": "Un programa se cierra solo o no abre",
        "categoria": Categoria.SOFTWARE,
        "etiquetas": "programa, se cierra, no abre, error, congela, actualizar",
        "resumen": "Qué probar cuando una aplicación falla al abrir o se congela.",
        "contenido": """1. Cierra completamente la aplicación (también desde la bandeja del sistema) y vuelve a abrirla.
2. Reinicia el equipo: resuelve la mayoría de bloqueos.
3. Comprueba si hay **actualizaciones pendientes** del programa o de Windows.
4. Si el fallo empezó tras una actualización, indícalo en el ticket con la fecha aproximada.

## Datos útiles para el ticket
- Nombre y versión del programa (*Ayuda → Acerca de*).
- El mensaje de error exacto o una captura.
- Qué estabas haciendo cuando falló.""",
    },
    {
        "titulo": "Cómo identificar un correo de phishing",
        "categoria": Categoria.SEGURIDAD,
        "etiquetas": "phishing, correo sospechoso, fraude, enlace, seguridad",
        "resumen": "Señales de alerta y qué hacer si ya hiciste clic en un enlace sospechoso.",
        "contenido": """## Señales de alerta
- Urgencia o amenazas: *"tu cuenta será bloqueada hoy"*.
- Remitentes que imitan dominios reales con pequeñas diferencias.
- Enlaces cuyo destino real no coincide con el texto (pasa el ratón por encima sin hacer clic).
- Solicitudes de contraseñas, códigos o datos bancarios. **Soporte nunca te los pedirá.**

## Si ya hiciste clic o escribiste tu contraseña
1. Cambia tu contraseña de inmediato.
2. Crea un ticket de *Seguridad* indicando la hora aproximada y adjunta el correo.
3. No borres el correo hasta que el equipo de seguridad lo revise.""",
    },
    {
        "titulo": "Configurar el correo corporativo en el móvil",
        "categoria": Categoria.OTROS,
        "etiquetas": "correo, móvil, outlook, sincronizar, teléfono",
        "resumen": "Añade tu cuenta en la app de Outlook para iOS o Android.",
        "contenido": """1. Instala **Microsoft Outlook** desde la tienda de aplicaciones.
2. Pulsa *Agregar cuenta* y escribe tu correo corporativo.
3. Inicia sesión con tu contraseña y aprueba la verificación si se solicita.
4. Acepta la política de seguridad del dispositivo cuando aparezca.

Si el correo no sincroniza, elimina la cuenta de la app y vuelve a agregarla.""",
    },
]

RESPUESTAS = [
    ("Saludo y toma del caso", None,
     "Hola {nombre}, soy {agente} y ya estoy revisando tu ticket {ticket}. Te mantendré al tanto por aquí."),
    ("Solicitar captura del error", None,
     "Hola {nombre}, para avanzar necesito una captura de pantalla del mensaje de error y la hora aproximada en que ocurrió. Puedes adjuntarla directamente en este ticket."),
    ("Confirmar solución", None,
     "Hola {nombre}, aplicamos la solución en el ticket {ticket}. ¿Puedes confirmar que ya funciona correctamente? Si no recibimos respuesta en 48 h lo cerraremos."),
    ("Restablecimiento de contraseña", Categoria.CUENTAS_CONTRASENAS,
     "Hola {nombre}, puedes restablecer tu contraseña tú mismo desde «¿Olvidaste tu contraseña?» en la pantalla de inicio de sesión. El enlace llega a tu correo y es válido 30 minutos."),
    ("Datos para revisar la VPN", Categoria.REDES,
     "Hola {nombre}, para diagnosticar la VPN indícanos: si estás por WiFi o cable, tu proveedor de internet y el resultado de ejecutar «ping vpn.empresa.com» en una terminal."),
    ("Aprobación de jefe directo", Categoria.PERMISOS,
     "Hola {nombre}, para conceder este acceso necesitamos la aprobación de tu jefe directo. Pídele que responda a este ticket confirmando el permiso solicitado."),
]

COMENTARIOS_CSAT = [
    "Muy rápido, gracias.", "Resolvieron todo en la primera llamada.", None, "Me explicaron cómo evitarlo en el futuro.",
    None, "Tardó un poco pero quedó bien.", None, "Excelente atención.",
]


def sembrar():
    autor = db.session.execute(
        select(Usuario).where(Usuario.rol == RolUsuario.ADMIN).order_by(Usuario.id)
    ).scalars().first()
    if autor is None:
        print("No hay administradores: ejecuta primero seed_admin.py")
        return

    creados = 0
    rnd = random.Random(7)
    for i, datos in enumerate(ARTICULOS):
        if db.session.execute(select(Articulo.id).where(Articulo.titulo == datos["titulo"])).first():
            continue
        fecha = datetime.now() - timedelta(days=40 - i * 3)
        util = rnd.randint(4, 30)
        db.session.add(Articulo(
            autor_id=autor.id, publicado=True, fecha_creacion=fecha, fecha_actualizacion=fecha,
            vistas=rnd.randint(30, 260), votos_utiles=util, votos_no_utiles=rnd.randint(0, util // 4),
            resoluciones=rnd.randint(0, 14), **datos,
        ))
        creados += 1

    respuestas = 0
    for titulo, categoria, contenido in RESPUESTAS:
        if db.session.execute(select(RespuestaPredefinida.id).where(RespuestaPredefinida.titulo == titulo)).first():
            continue
        db.session.add(RespuestaPredefinida(
            titulo=titulo, categoria=categoria, contenido=contenido, compartida=True,
            autor_id=autor.id, usos=rnd.randint(0, 25),
        ))
        respuestas += 1
    db.session.commit()

    cerrados = db.session.execute(
        select(Ticket).where(Ticket.estado == EstadoTicket.CERRADO, Ticket.agente_id.isnot(None))
        .order_by(Ticket.fecha_cierre.desc())
    ).scalars().all()
    encuestas = 0
    for indice, ticket in enumerate(cerrados):
        if indice % 4 == 3:
            continue
        if db.session.execute(select(EncuestaSatisfaccion.id).where(EncuestaSatisfaccion.ticket_id == ticket.id)).first():
            continue
        puntuacion = rnd.choices([5, 4, 3, 2, 1], weights=[45, 30, 12, 8, 5])[0]
        db.session.add(EncuestaSatisfaccion(
            ticket_id=ticket.id, usuario_id=ticket.creador_id, agente_id=ticket.agente_id,
            puntuacion=puntuacion, comentario=COMENTARIOS_CSAT[indice % len(COMENTARIOS_CSAT)],
            fecha=(ticket.fecha_cierre or datetime.now()) + timedelta(hours=2),
        ))
        tiene_respuesta = db.session.execute(
            select(Comentario.id).where(Comentario.ticket_id == ticket.id, Comentario.autor_id == ticket.agente_id)
        ).first()
        if not tiene_respuesta and ticket.fecha_asignacion:
            db.session.add(Comentario(
                ticket_id=ticket.id, autor_id=ticket.agente_id,
                texto="Estoy revisando tu caso, te escribo en cuanto tenga novedades.",
                fecha=ticket.fecha_asignacion + timedelta(minutes=rnd.randint(10, 180)),
            ))
            db.session.add(Comentario(
                ticket_id=ticket.id, autor_id=ticket.agente_id, interno=True,
                texto="Revisado el historial del equipo: sin incidencias previas similares.",
                fecha=ticket.fecha_asignacion + timedelta(minutes=rnd.randint(181, 300)),
            ))
        encuestas += 1
    db.session.commit()
    print(f"Base de conocimiento: {creados} artículos · respuestas rápidas: {respuestas} · encuestas: {encuestas}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        sembrar()
