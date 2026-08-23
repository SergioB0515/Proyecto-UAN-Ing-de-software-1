from app.Models.enum import NivelUsuario
from sqlalchemy import select
from app import db
from app.Models.usuario import Usuario
import bcrypt
class ServicioAutenticacion:
  
    @staticmethod
    def registrar(nombre, email, contrasena, rol, area_soporte=None, nivel=NivelUsuario.NORMAL):
        existe =db.session.execute(select(Usuario.email).where(Usuario.email ==email)).scalar() is not None
        if existe:
            return False
        
        hash_contrasena=ServicioAutenticacion._generar_hash(contrasena)
    
        nuevo_usuario= Usuario(
            nombre=nombre,
            contrasena_hash=hash_contrasena,
            rol=rol,
            email=email,
            area_soporte=area_soporte,
            nivel=nivel
        )
        
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            print(f"El usuario {nombre} se ha resgistrado con exito")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido realizar el guardado u registro error : {e}")  
            return False
        
    
    @staticmethod
    def _generar_hash(contrasena_plana):
        contrasena_byte=contrasena_plana.encode("utf-8")
        sal=bcrypt.gensalt()
        hash_contrasena = bcrypt.hashpw(contrasena_byte,sal)
        return hash_contrasena.decode("utf-8")


    @staticmethod
    def _verificar_contrasena(contrasena_plana, hash_guardado):
        return bcrypt.checkpw(
        contrasena_plana.encode("utf-8"),
        hash_guardado.encode("utf-8")
    )
      
        

    @staticmethod
    def iniciar_sesion(email, contrasena):
        ...



        

    @staticmethod
    def esta_bloqueado(usuario):
        ...