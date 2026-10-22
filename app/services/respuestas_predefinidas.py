from flask_babel import gettext as _
from sqlalchemy import select, or_

from app.extensions import db
from app.models.enum import AccionAuditoria, Categoria, RolUsuario
from app.models.respuesta_predefinida import RespuestaPredefinida
from app.models.usuario import Usuario
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import ErrorPersistencia, PermisoDenegadoError, RespuestaNoEncontradaError

VARIABLES = ("{nombre}", "{ticket}", "{agente}", "{categoria}")


def aplicar_variables(contenido, nombre="", ticket="", agente="", categoria=""):
    valores = {"{nombre}": nombre, "{ticket}": f"#{ticket}" if ticket else "", "{agente}": agente, "{categoria}": categoria}
    for clave, valor in valores.items():
        contenido = contenido.replace(clave, str(valor))
    return contenido


class ServicioRespuestasPredefinidas:

    @staticmethod
    def _guardar(mensaje):
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"{mensaje}, error: {e}")
            raise ErrorPersistencia(mensaje) from e

    @staticmethod
    def _autor_valido(usuario_id):
        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None or usuario.rol not in (RolUsuario.AGENTE, RolUsuario.ADMIN):
            raise PermisoDenegadoError(_("Solo agentes y administradores pueden usar respuestas predefinidas"))
        return usuario

    @staticmethod
    def _validar(titulo, contenido, categoria):
        titulo = (titulo or "").strip()
        contenido = (contenido or "").strip()
        if len(titulo) < 3:
            raise ValueError(_("El título debe tener al menos %(n)s caracteres", n=3))
        if len(titulo) > 120:
            raise ValueError(_("El título no puede superar los 120 caracteres"))
        if len(contenido) < 5:
            raise ValueError(_("El contenido debe tener al menos %(n)s caracteres", n=5))
        if categoria is not None and not isinstance(categoria, Categoria):
            raise ValueError(_("Categoría no válida"))
        return titulo, contenido

    @staticmethod
    def listar_para(usuario_id, categoria=None):
        query = select(RespuestaPredefinida).where(
            or_(RespuestaPredefinida.compartida.is_(True), RespuestaPredefinida.autor_id == usuario_id)
        )
        if categoria is not None:
            query = query.where(or_(RespuestaPredefinida.categoria.is_(None), RespuestaPredefinida.categoria == categoria))
        return db.session.execute(
            query.order_by(RespuestaPredefinida.usos.desc(), RespuestaPredefinida.titulo)
        ).scalars().all()

    @staticmethod
    def obtener_para(respuesta_id, usuario_id):
        respuesta = db.session.get(RespuestaPredefinida, respuesta_id)
        if respuesta is None or (not respuesta.compartida and respuesta.autor_id != usuario_id):
            raise RespuestaNoEncontradaError(_("La respuesta predefinida no existe"))
        return respuesta

    @staticmethod
    def _puede_editar(respuesta, usuario):
        return usuario.rol == RolUsuario.ADMIN or respuesta.autor_id == usuario.id

    @staticmethod
    def crear(autor_id, titulo, contenido, categoria=None, compartida=True):
        ServicioRespuestasPredefinidas._autor_valido(autor_id)
        titulo, contenido = ServicioRespuestasPredefinidas._validar(titulo, contenido, categoria)
        respuesta = RespuestaPredefinida(
            titulo=titulo, contenido=contenido, categoria=categoria,
            compartida=bool(compartida), autor_id=autor_id,
        )
        db.session.add(respuesta)
        ServicioRespuestasPredefinidas._guardar(_("No se pudo crear la respuesta predefinida"))
        ServicioAuditoria.registrar(
            usuario_id=autor_id,
            accion=AccionAuditoria.CREAR_RESPUESTA_PREDEFINIDA,
            detalle=_("Respuesta predefinida creada: %(p1)s", p1=titulo),
        )
        return respuesta

    @staticmethod
    def actualizar(actor_id, respuesta_id, titulo, contenido, categoria=None, compartida=True):
        actor = ServicioRespuestasPredefinidas._autor_valido(actor_id)
        respuesta = ServicioRespuestasPredefinidas.obtener_para(respuesta_id, actor_id)
        if not ServicioRespuestasPredefinidas._puede_editar(respuesta, actor):
            raise PermisoDenegadoError(_("Solo el autor o un administrador puede modificar esta respuesta"))
        titulo, contenido = ServicioRespuestasPredefinidas._validar(titulo, contenido, categoria)
        respuesta.titulo = titulo
        respuesta.contenido = contenido
        respuesta.categoria = categoria
        respuesta.compartida = bool(compartida)
        ServicioRespuestasPredefinidas._guardar(_("No se pudo actualizar la respuesta predefinida"))
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.EDITAR_RESPUESTA_PREDEFINIDA,
            detalle=_("Respuesta predefinida editada: %(p1)s", p1=titulo),
        )
        return respuesta

    @staticmethod
    def eliminar(actor_id, respuesta_id):
        actor = ServicioRespuestasPredefinidas._autor_valido(actor_id)
        respuesta = ServicioRespuestasPredefinidas.obtener_para(respuesta_id, actor_id)
        if not ServicioRespuestasPredefinidas._puede_editar(respuesta, actor):
            raise PermisoDenegadoError(_("Solo el autor o un administrador puede eliminar esta respuesta"))
        titulo = respuesta.titulo
        db.session.delete(respuesta)
        ServicioRespuestasPredefinidas._guardar(_("No se pudo eliminar la respuesta predefinida"))
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.ELIMINAR_RESPUESTA_PREDEFINIDA,
            detalle=_("Respuesta predefinida eliminada: %(p1)s", p1=titulo),
        )
        return True

    @staticmethod
    def registrar_uso(respuesta_id, usuario_id):
        respuesta = ServicioRespuestasPredefinidas.obtener_para(respuesta_id, usuario_id)
        respuesta.usos = (respuesta.usos or 0) + 1
        ServicioRespuestasPredefinidas._guardar(_("No se pudo registrar el uso"))
        return respuesta
