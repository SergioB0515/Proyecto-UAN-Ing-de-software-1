from app.extensions import db
from app.models.palabra_clave import PalabraClave
from flask_babel import gettext as _
from sqlalchemy import select
from app.services.auditoria import ServicioAuditoria
from app.services.clasificacion_avanzada import invalidar_cache_palabras_clave
from app.models.enum import Categoria, AccionAuditoria
from app.services.exceptions import PalabraClaveDuplicadaError, ErrorPersistencia, PalabraClaveNoEncontradaError


class ServicioPalabraClave:

    @staticmethod
    def listar_palabras_clave(incluir_inactivas: bool = False) -> list[PalabraClave]:
        query = select(PalabraClave)
        if not incluir_inactivas:
            query = query.where(PalabraClave.activa == True)
        return db.session.execute(query).scalars().all()

    @staticmethod
    def crear_palabra_clave(texto: str, categoria: Categoria, peso: float, actor_id) -> PalabraClave:
        texto = texto.lower().strip()

        palabra_existente = db.session.execute(
            select(PalabraClave).where(
                PalabraClave.texto == texto,
                PalabraClave.categoria == categoria,
                PalabraClave.activa == True
            )
        ).scalar()

        if palabra_existente:
            raise PalabraClaveDuplicadaError(_("Esta palabra clave ya se encuentra registrada"))

        palabra_nueva = PalabraClave(categoria=categoria, texto=texto, peso=peso, activa=True)
        try:
            db.session.add(palabra_nueva)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido agregar la palabra clave, error : {e}")
            raise ErrorPersistencia(_("No se pudo agregar la palabra clave")) from e

        invalidar_cache_palabras_clave()

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.CREAR_PALABRA_CLAVE,
            detalle=_("palabra #%(p1)s creada: categoria=%(p2)s, peso=%(p3)s", p1=palabra_nueva.id, p2=palabra_nueva.categoria, p3=palabra_nueva.peso),
        )
        return palabra_nueva

    @staticmethod
    def editar_palabra_clave(id: int, texto: str, categoria: Categoria, peso: float, actor_id) -> PalabraClave:
        texto = texto.lower().strip()

        palabra = db.session.execute(
            select(PalabraClave).where(PalabraClave.id == id, PalabraClave.activa == True)
        ).scalar()
        if not palabra:
            raise PalabraClaveNoEncontradaError(_("No se ha encontrado la palabra clave"))

        palabra_existente = db.session.execute(
            select(PalabraClave).where(
                PalabraClave.id != id,
                PalabraClave.texto == texto,
                PalabraClave.categoria == categoria,
                PalabraClave.activa == True
            )
        ).scalar()

        if palabra_existente:
            raise PalabraClaveDuplicadaError(_("Esta palabra clave ya se encuentra registrada"))

        palabra.texto = texto
        palabra.categoria = categoria
        palabra.peso = peso
        try:
            db.session.add(palabra)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido editar la palabra clave, error : {e}")
            raise ErrorPersistencia(_("No se pudo editar la palabra clave")) from e

        invalidar_cache_palabras_clave()

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.EDITAR_PALABRA_CLAVE,
            detalle=_("palabra #%(p1)s editada: categoria=%(p2)s, peso=%(p3)s", p1=palabra.id, p2=palabra.categoria, p3=palabra.peso),
        )
        return palabra

    @staticmethod
    def desactivar_palabra_clave(id: int, actor_id) -> PalabraClave:
        palabra = db.session.execute(
            select(PalabraClave).where(PalabraClave.id == id, PalabraClave.activa == True)
        ).scalar()
        if not palabra:
            raise PalabraClaveNoEncontradaError(_("No se ha encontrado la palabra clave"))

        palabra.activa = False
        try:
            db.session.add(palabra)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido desactivar la palabra clave, error : {e}")
            raise ErrorPersistencia(_("No se pudo desactivar la palabra clave")) from e

        invalidar_cache_palabras_clave()

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.DESACTIVAR_PALABRA_CLAVE,
            detalle=_("palabra #%(p1)s desactivada", p1=palabra.id),
        )
        return palabra

    @staticmethod
    def reactivar_palabra_clave(id: int, actor_id) -> PalabraClave:
        palabra = db.session.execute(
            select(PalabraClave).where(PalabraClave.id == id, PalabraClave.activa == False)
        ).scalar()
        if not palabra:
            raise PalabraClaveNoEncontradaError(_("No se ha encontrado la palabra clave"))

        palabra_existente = db.session.execute(
            select(PalabraClave).where(
                PalabraClave.id != id,
                PalabraClave.texto == palabra.texto,
                PalabraClave.categoria == palabra.categoria,
                PalabraClave.activa == True
            )
        ).scalar()
        if palabra_existente:
            raise PalabraClaveDuplicadaError(_("Ya existe una palabra clave activa con el mismo texto y categoría"))

        palabra.activa = True
        try:
            db.session.add(palabra)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido reactivar la palabra clave, error : {e}")
            raise ErrorPersistencia(_("No se pudo reactivar la palabra clave")) from e

        invalidar_cache_palabras_clave()

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.REACTIVAR_PALABRA_CLAVE,
            detalle=_("palabra #%(p1)s reactivada", p1=palabra.id),
        )
        return palabra