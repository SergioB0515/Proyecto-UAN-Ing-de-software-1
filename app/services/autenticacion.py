from app.models.enum import NivelUsuario, AccionAuditoria
from sqlalchemy import select
from app.extensions import db
from app.models.usuario import Usuario
from datetime import datetime,timedelta
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import ErrorPersistencia
import bcrypt
class ResultadoLogin:
    EXITOSO = "exitoso"
    CREDENCIALES_INVALIDAS = "credenciales_invalidas"      
    BLOQUEADO_AHORA = "bloqueado_ahora"                       
    YA_BLOQUEADO = "ya_bloqueado"                             
    USUARIO_NO_EXISTE = "usuario_no_existe"
    ERROR_INTERNO = "error_interno"
class ServicioAutenticacion:
  
    @staticmethod
    def registrar(nombre, email, contrasena, rol, admin_id, area_soporte=None, nivel=NivelUsuario.NORMAL):
        existe =db.session.execute(select(Usuario.email).where(Usuario.email ==email)).scalar() is not None
        if existe:
            return None

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
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido registrar al usuario, error : {e}")
            raise ErrorPersistencia("No se pudo registrar al usuario") from e

        print(f"El usuario {nombre} se ha resgistrado con exito")
        ServicioAuditoria.registrar(
            usuario_id=admin_id,
            accion=AccionAuditoria.REGISTRO_EXITOSO,
            detalle=f"Se registro al usuario {nuevo_usuario.email} (rol={rol}, nivel={nivel})",
        )
        return nuevo_usuario
        
    
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

        if usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta < datetime.now():
            usuario.bloqueado_hasta = None
            usuario.intentos_fallidos = 0
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"No se ha podido levantar el bloqueo del usuario, error: {e}")
                return None, ResultadoLogin.ERROR_INTERNO
            ServicioAuditoria.registrar(
                usuario_id=usuario.id,
                accion=AccionAuditoria.DESBLOQUEO_USUARIO,
                detalle=f"Se levanto el bloqueo para {usuario.email}",
            )
        elif ServicioAutenticacion.esta_bloqueado(usuario):
            return None, ResultadoLogin.YA_BLOQUEADO

        password = ServicioAutenticacion._verificar_contrasena(contrasena,usuario.contrasena_hash)

        if not password:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= 3:
                usuario.bloqueado_hasta = datetime.now() + timedelta(hours=5)
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"No se ha podido bloquear al usuario, error: {e}")
                    return None, ResultadoLogin.ERROR_INTERNO
                ServicioAuditoria.registrar(
                    usuario_id=usuario.id,
                    accion=AccionAuditoria.CUENTA_BLOQUEADA,
                    detalle=f"Cuenta bloqueada por 3 intentos fallidos: {usuario.email}"
                )
                return None, ResultadoLogin.BLOQUEADO_AHORA
            else:
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"No se ha podido registrar el intento fallido, error: {e}")
                    return None, ResultadoLogin.ERROR_INTERNO
                ServicioAuditoria.registrar(
                    usuario_id=usuario.id,
                    accion=AccionAuditoria.LOGIN_FALLIDO,
                    detalle=f"Intento fallido de login para {usuario.email} (intento {usuario.intentos_fallidos})"
            )
                return None, ResultadoLogin.CREDENCIALES_INVALIDAS

        usuario.intentos_fallidos = 0
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido loguear al usuario error: {e}")
            return None, ResultadoLogin.ERROR_INTERNO
        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.LOGIN_EXITOSO,
            detalle=f"Login exitoso para {usuario.email}",
        )
        return usuario, ResultadoLogin.EXITOSO


        

    @staticmethod
    def esta_bloqueado(usuario):
        if usuario.bloqueado_hasta is None :
            return False
        elif usuario.bloqueado_hasta > datetime.now():
            return True
        else:
            return False
    @staticmethod
    def cambiar_contrasena(usuario, contrasena_actual, contrasena_nueva):

        correcto = ServicioAutenticacion._verificar_contrasena(contrasena_actual, usuario.contrasena_hash)
        if not correcto:
            raise ValueError("la contraseña actual es incorrecta")

        if contrasena_nueva == contrasena_actual:
            raise ValueError("La nueva contraseña debe ser distinta a la actual")

        usuario.contrasena_hash = ServicioAutenticacion._generar_hash(contrasena_nueva)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            db.session.refresh(usuario)
            raise ErrorPersistencia("No se pudo guardar el cambio de contraseña") from e

        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.CAMBIO_CONTRASENA,
            detalle=f"Se realizó un cambio de contraseña para el usuario: {usuario.id}"
        )

        return True