from app.Models.log_auditoria import LogAuditoria
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
            return True,nuevo_log
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido realizar el guardado u registro error : {e}")  
            
            try:
                db.session.add(nuevo_log)
                db.session.commit()
                print(f"El log ha sido creado con exito")
                return True,nuevo_log
            except Exception as e2:
                db.session.rollback()
                print(f"Fallo tambien el reintento, se perdio este registro de auditoria. error: {e2}")
                return False, None  
   