from app.models.log_auditoria import LogAuditoria
from sqlalchemy import select
from app.extensions import db
class ServicioAuditoria:

    @staticmethod
    def registrar(usuario_id, accion, detalle):


        nuevo_log = LogAuditoria(
            usuario_id=usuario_id,
            accion=accion,
            detalle=detalle
        )

        try:
            db.session.add(nuevo_log)
            db.session.commit()
            print(f"El log ha sido creado con exito")
            return nuevo_log
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido guardar el registro de auditoria, error : {e}")

            try:
                db.session.add(nuevo_log)
                db.session.commit()
                print(f"El log ha sido creado con exito")
                return nuevo_log
            except Exception as e2:
                db.session.rollback()
                print(f"Fallo tambien el reintento, se perdio este registro de auditoria. error: {e2}")
                return None
            
    @staticmethod
    def listar_logs(usuario_id=None, accion=None, fecha_desde=None, fecha_hasta=None, pagina=1, por_pagina=35):

        query = select(LogAuditoria)

        if usuario_id is not None:
            query = query.where(LogAuditoria.usuario_id == usuario_id)

        if accion is not None:
            query = query.where(LogAuditoria.accion == accion)

        if fecha_desde is not None:
            query = query.where(LogAuditoria.fecha >= fecha_desde)

        if fecha_hasta is not None:
            query = query.where(LogAuditoria.fecha < fecha_hasta)

        query = query.order_by(LogAuditoria.fecha.desc())
        resultado = db.paginate(query, page=pagina, per_page=por_pagina)
        return resultado

    @staticmethod
    def listar_logs(usuario_id=None, accion=None, fecha_desde=None, fecha_hasta=None, pagina=1, por_pagina=35, sin_paginar=False):
        query = select(LogAuditoria)

        if usuario_id is not None:
            query = query.where(LogAuditoria.usuario_id == usuario_id)
        if accion is not None:
            query = query.where(LogAuditoria.accion == accion)
        if fecha_desde is not None:
            query = query.where(LogAuditoria.fecha >= fecha_desde)
        if fecha_hasta is not None:
            query = query.where(LogAuditoria.fecha < fecha_hasta)

        query = query.order_by(LogAuditoria.fecha.desc())


        if sin_paginar:
            return db.session.execute(query).scalars().all()

        resultado = db.paginate(query, page=pagina, per_page=por_pagina)
        return resultado
