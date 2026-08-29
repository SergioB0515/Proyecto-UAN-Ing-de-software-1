from app.models.enum import Categoria

PALABRAS_CLAVE = {
    Categoria.SEGURIDAD: ["no fui yo", "alguien entró", "correo sospechoso", "movimiento raro", "phishing", "me robaron", "actividad extraña"],
    Categoria.REDES: ["no hay wifi", "no tengo internet", "no carga nada", "sin conexión", "se cae la red", "muy lento internet"],
    Categoria.INFRAESTRUCTURA: ["no enciende", "se apaga solo", "pantalla azul", "no prende", "dañado", "roto", "no funciona el mouse", "no funciona el teclado"],
    Categoria.PERMISOS: ["no puedo entrar a", "no tengo acceso a", "acceso denegado", "no me deja ver", "no puedo abrir la carpeta"],
    Categoria.CUENTAS_CONTRASENAS: ["olvidé mi contraseña", "no puedo iniciar sesión", "cuenta bloqueada", "cambiar contraseña", "contraseña incorrecta"],
    Categoria.SOFTWARE: ["se cierra solo", "no abre el programa", "error al abrir", "no guarda", "se congela", "no sincroniza"],
}
class ClasificadorTickets:
    @staticmethod
    def clasificar(texto):
        texto_listo=texto.lower()
        for categoria, palabras in PALABRAS_CLAVE.items():
            if any(palabra in texto_listo for palabra in palabras):
                return categoria
        return Categoria.OTROS