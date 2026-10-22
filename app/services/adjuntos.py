import os
import uuid

from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import select, func
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.adjunto import Adjunto
from app.models.enum import AccionAuditoria, RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    AdjuntoInvalidoError,
    AdjuntoNoEncontradoError,
    ErrorPersistencia,
    PermisoDenegadoError,
    TicketNoEncontradoError,
)

TAMANO_MAXIMO_BYTES = 5 * 1024 * 1024
MAX_ADJUNTOS_POR_TICKET = 10
TIPOS_PERMITIDOS = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "log": "text/plain",
    "csv": "text/csv",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}
FIRMAS = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "pdf": (b"%PDF-",),
    "docx": (b"PK\x03\x04",),
    "xlsx": (b"PK\x03\x04",),
    "zip": (b"PK\x03\x04", b"PK\x05\x06"),
}
EXTENSIONES_TEXTO = {"txt", "log", "csv"}


def carpeta_adjuntos():
    carpeta = current_app.config.get("CARPETA_ADJUNTOS") or os.path.join(current_app.instance_path, "adjuntos")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _contenido_coincide(extension, cabecera):
    if extension == "webp":
        return cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP"
    if extension in EXTENSIONES_TEXTO:
        return b"\x00" not in cabecera
    return any(cabecera.startswith(f) for f in FIRMAS.get(extension, ()))


def formato_tamano(bytes_):
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"


class ServicioAdjuntos:

    @staticmethod
    def listar(ticket_id):
        return db.session.execute(
            select(Adjunto).where(Adjunto.ticket_id == ticket_id).order_by(Adjunto.fecha)
        ).scalars().all()

    @staticmethod
    def obtener(adjunto_id):
        adjunto = db.session.get(Adjunto, adjunto_id)
        if adjunto is None:
            raise AdjuntoNoEncontradoError(_("El archivo no existe"))
        return adjunto

    @staticmethod
    def ruta(adjunto):
        return os.path.join(carpeta_adjuntos(), adjunto.nombre_guardado)

    @staticmethod
    def guardar(ticket_id, usuario_id, archivo, comentario_id=None):
        ticket = db.session.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))

        if archivo is None or not getattr(archivo, "filename", ""):
            raise AdjuntoInvalidoError(_("No se seleccionó ningún archivo"))

        nombre_original = os.path.basename(archivo.filename.replace("\\", "/"))[:255]
        seguro = secure_filename(nombre_original)
        extension = os.path.splitext(nombre_original)[1].lower().lstrip(".")
        if extension not in TIPOS_PERMITIDOS:
            raise AdjuntoInvalidoError(
                _("Tipo de archivo no permitido. Formatos aceptados: %(f)s", f=", ".join(sorted(TIPOS_PERMITIDOS)))
            )

        existentes = db.session.execute(select(func.count(Adjunto.id)).where(Adjunto.ticket_id == ticket_id)).scalar()
        if existentes >= MAX_ADJUNTOS_POR_TICKET:
            raise AdjuntoInvalidoError(_("El ticket ya tiene el máximo de %(n)s archivos", n=MAX_ADJUNTOS_POR_TICKET))

        datos = archivo.read(TAMANO_MAXIMO_BYTES + 1)
        if len(datos) == 0:
            raise AdjuntoInvalidoError(_("El archivo está vacío"))
        if len(datos) > TAMANO_MAXIMO_BYTES:
            raise AdjuntoInvalidoError(_("El archivo supera el tamaño máximo de %(t)s", t=formato_tamano(TAMANO_MAXIMO_BYTES)))
        if not _contenido_coincide(extension, datos[:16]):
            raise AdjuntoInvalidoError(_("El contenido del archivo no corresponde a su extensión"))

        nombre_guardado = f"{uuid.uuid4().hex}.{extension}"
        ruta = os.path.join(carpeta_adjuntos(), nombre_guardado)
        with open(ruta, "wb") as destino:
            destino.write(datos)

        adjunto = Adjunto(
            ticket_id=ticket_id,
            comentario_id=comentario_id,
            usuario_id=usuario_id,
            nombre_original=nombre_original or seguro or nombre_guardado,
            nombre_guardado=nombre_guardado,
            tipo_mime=TIPOS_PERMITIDOS[extension],
            tamano=len(datos),
        )
        db.session.add(adjunto)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            if os.path.exists(ruta):
                os.remove(ruta)
            print(f"No se pudo guardar el adjunto, error: {e}")
            raise ErrorPersistencia(_("No se pudo guardar el archivo")) from e

        ServicioAuditoria.registrar(
            usuario_id=usuario_id,
            accion=AccionAuditoria.SUBIR_ADJUNTO,
            detalle=_("Archivo «%(p1)s» adjuntado al ticket #%(p2)s", p1=adjunto.nombre_original, p2=ticket_id),
        )
        return adjunto

    @staticmethod
    def eliminar(adjunto_id, actor_id):
        adjunto = ServicioAdjuntos.obtener(adjunto_id)
        actor = db.session.get(Usuario, actor_id)
        if actor is None or (actor.rol != RolUsuario.ADMIN and adjunto.usuario_id != actor_id):
            raise PermisoDenegadoError(_("Solo quien subió el archivo o un administrador puede eliminarlo"))
        ruta = ServicioAdjuntos.ruta(adjunto)
        ticket_id, nombre = adjunto.ticket_id, adjunto.nombre_original
        db.session.delete(adjunto)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo eliminar el adjunto, error: {e}")
            raise ErrorPersistencia(_("No se pudo eliminar el archivo")) from e
        if os.path.exists(ruta):
            os.remove(ruta)
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.ELIMINAR_ADJUNTO,
            detalle=_("Archivo «%(p1)s» eliminado del ticket #%(p2)s", p1=nombre, p2=ticket_id),
        )
        return True
