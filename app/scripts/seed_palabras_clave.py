from app import create_app
from app.extensions import db
from app.models.palabra_clave import PalabraClave
from app.models.enum import Categoria

PALABRAS = [
    # --- SEGURIDAD ---
    ("no fui yo", Categoria.SEGURIDAD, 1.5),
    ("alguien entró", Categoria.SEGURIDAD, 2.0),
    ("alguien tiene mi contraseña", Categoria.SEGURIDAD, 2.5),
    ("me robaron", Categoria.SEGURIDAD, 2.2),
    ("hackearon", Categoria.SEGURIDAD, 2.5),
    ("correo sospechoso", Categoria.SEGURIDAD, 1.8),
    ("correo falso", Categoria.SEGURIDAD, 1.8),
    ("phishing", Categoria.SEGURIDAD, 2.5),
    ("actividad extraña", Categoria.SEGURIDAD, 1.5),
    ("movimiento raro", Categoria.SEGURIDAD, 1.5),
    ("nota de rescate", Categoria.SEGURIDAD, 2.5),
    ("archivos encriptados", Categoria.SEGURIDAD, 2.0),
    ("ransomware", Categoria.SEGURIDAD, 2.5),
    ("virus", Categoria.SEGURIDAD, 1.8),
    ("intento de conexión", Categoria.SEGURIDAD, 1.5),
    ("configuró reglas en mi correo", Categoria.SEGURIDAD, 2.0),

    # --- REDES ---
    ("no hay wifi", Categoria.REDES, 2.0),
    ("no tengo internet", Categoria.REDES, 2.0),
    ("sin conexión", Categoria.REDES, 1.5),
    ("red caída", Categoria.REDES, 1.8),
    ("vpn", Categoria.REDES, 1.5),
    ("no conecta a la red", Categoria.REDES, 1.8),
    ("no obtiene dirección ip", Categoria.REDES, 2.0),
    ("dhcp", Categoria.REDES, 1.8),
    ("puerto ethernet", Categoria.REDES, 1.8),
    ("ping alto", Categoria.REDES, 1.5),
    ("wifi lento", Categoria.REDES, 1.2),
    ("firmware del router", Categoria.REDES, 1.8),

    # --- INFRAESTRUCTURA ---
    ("no enciende", Categoria.INFRAESTRUCTURA, 2.0),
    ("se apaga solo", Categoria.INFRAESTRUCTURA, 1.8),
    ("pantalla azul", Categoria.INFRAESTRUCTURA, 2.2),
    ("pantalla negra", Categoria.INFRAESTRUCTURA, 1.5),
    ("no prende", Categoria.INFRAESTRUCTURA, 2.0),
    ("mouse no responde", Categoria.INFRAESTRUCTURA, 1.5),
    ("teclado no responde", Categoria.INFRAESTRUCTURA, 1.5),
    ("impresora no imprime", Categoria.INFRAESTRUCTURA, 1.8),
    ("disco duro", Categoria.INFRAESTRUCTURA, 1.5),
    ("led rojo", Categoria.INFRAESTRUCTURA, 1.5),
    ("pitidos", Categoria.INFRAESTRUCTURA, 1.8),
    ("batería se descarga", Categoria.INFRAESTRUCTURA, 1.5),
    ("ventilador", Categoria.INFRAESTRUCTURA, 1.2),
    ("pantalla descalibrada", Categoria.INFRAESTRUCTURA, 1.8),

    # --- PERMISOS (peso alto = "acceso a recurso especifico") ---
    ("no puedo entrar a", Categoria.PERMISOS, 1.2),   # generico, peso mas bajo
    ("no tengo acceso a", Categoria.PERMISOS, 1.5),
    ("acceso denegado", Categoria.PERMISOS, 1.8),
    ("no me deja ver", Categoria.PERMISOS, 1.5),
    ("no puedo abrir la carpeta", Categoria.PERMISOS, 2.0),
    ("usuario sin privilegios", Categoria.PERMISOS, 2.2),
    ("carpeta restringida", Categoria.PERMISOS, 2.0),
    ("me deniega la ejecución", Categoria.PERMISOS, 2.0),
    ("falta de roles", Categoria.PERMISOS, 2.0),
    ("no tengo permisos para", Categoria.PERMISOS, 2.0),
    ("restricción de lectura", Categoria.PERMISOS, 1.8),

    # --- CUENTAS_CONTRASENAS (peso alto = mencion explicita de contraseña/clave) ---
    ("olvidé mi contraseña", Categoria.CUENTAS_CONTRASENAS, 2.2),
    ("cuenta bloqueada", Categoria.CUENTAS_CONTRASENAS, 2.0),
    ("contraseña incorrecta", Categoria.CUENTAS_CONTRASENAS, 2.2),
    ("no recuerdo mi clave", Categoria.CUENTAS_CONTRASENAS, 2.2),
    ("cambiar mi contraseña", Categoria.CUENTAS_CONTRASENAS, 2.0),
    ("usuario no reconocido", Categoria.CUENTAS_CONTRASENAS, 1.8),
    ("cuenta suspendida", Categoria.CUENTAS_CONTRASENAS, 1.8),
    ("perfil inhabilitado", Categoria.CUENTAS_CONTRASENAS, 1.8),
    ("no hay cuenta asociada", Categoria.CUENTAS_CONTRASENAS, 2.0),
    ("código de recuperación", Categoria.CUENTAS_CONTRASENAS, 2.0),
    ("relación de confianza con el dominio", Categoria.CUENTAS_CONTRASENAS, 2.0),

    # --- SOFTWARE ---
    ("se cierra solo", Categoria.SOFTWARE, 1.8),
    ("no abre el programa", Categoria.SOFTWARE, 2.0),
    ("no abre la aplicación", Categoria.SOFTWARE, 2.0),
    ("se congela", Categoria.SOFTWARE, 1.5),
    ("error al guardar", Categoria.SOFTWARE, 1.8),
    ("no sincroniza", Categoria.SOFTWARE, 1.5),
    ("archivo dll faltante", Categoria.SOFTWARE, 2.0),
    ("error de servidor 500", Categoria.SOFTWARE, 1.8),
    ("versión desactualizada", Categoria.SOFTWARE, 1.2),
    ("no detecta la cámara", Categoria.SOFTWARE, 1.5),
    ("consume demasiada memoria", Categoria.SOFTWARE, 1.5),
]


def sembrar():
    if PalabraClave.query.first():
        print("Ya existen palabras clave sembradas. No se siembra de nuevo.")
        return

    for texto, categoria, peso in PALABRAS:
        db.session.add(PalabraClave(texto=texto, categoria=categoria, peso=peso))
    db.session.commit()
    print(f"{len(PALABRAS)} palabras clave sembradas.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        sembrar()