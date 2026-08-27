from app.Models.enum import NivelUsuario
from sqlalchemy import select
from app.extensions import db
from app.Models.usuario import Usuario
from datetime import datetime,timedelta
import bcrypt
class ResultadoLogin:
    EXITOSO = "exitoso"
    CREDENCIALES_INVALIDAS = "credenciales_invalidas"       # falló, quedan intentos
    BLOQUEADO_AHORA = "bloqueado_ahora"                       # este intento causó el bloqueo
    YA_BLOQUEADO = "ya_bloqueado"                             # llegó bloqueado desde antes
    USUARIO_NO_EXISTE = "usuario_no_existe"
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
        usuario = db.session.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()
        if usuario is None:
            return None, ResultadoLogin.USUARIO_NO_EXISTE

        elif ServicioAutenticacion.esta_bloqueado(usuario):
            return None, ResultadoLogin.YA_BLOQUEADO

        password = ServicioAutenticacion._verificar_contrasena(contrasena,usuario.contrasena_hash)

        if not password:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos == 5:
                usuario.bloqueado_hasta = datetime.now() + timedelta(hours=5)
                db.session.commit()
                return None, ResultadoLogin.BLOQUEADO_AHORA
            else:
                db.session.commit()
                return None, ResultadoLogin.CREDENCIALES_INVALIDAS

        usuario.intentos_fallidos = 0
        db.session.commit()
        return usuario, ResultadoLogin.EXITOSO


        

    @staticmethod
    def esta_bloqueado(usuario):
        if usuario.bloqueado_hasta is None :
            return False
        elif usuario.bloqueado_hasta > datetime.now():
            return True
        else:
            return True