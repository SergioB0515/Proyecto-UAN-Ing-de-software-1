from app.Models.enum import NivelUsuario 
import bcrypt
class ServicioAutenticacion:
    @staticmethod
    def registrar(nombre, email, contrasena, rol, area_soporte=None, nivel=NivelUsuario.NORMAL):
        ...

    @staticmethod
    def iniciar_sesion(email, contrasena):
        ...

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
    def esta_bloqueado(usuario):
        ...