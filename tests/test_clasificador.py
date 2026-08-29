"""
Script de prueba manual para ClasificadorTickets.clasificar()

Como correrlo (desde la carpeta Proyecto, con el entorno virtual activado):
    python -m tests.test_clasificador

Que verifica:
1. Que cada categoria se detecta correctamente con un texto claro y sin ambiguedad.
2. Que un texto sin ninguna palabra clave conocida cae en OTROS.
3. El caso de ambiguedad Permisos vs Cuentas_contrasenas: por el orden de
   criticidad definido, Permisos debe ganar siempre, incluso si el texto
   menciona "contraseña" explicitamente.
"""

from app.services.clasificador import ClasificadorTickets
from app.models.enum import Categoria


CASOS_UNA_SOLA_CATEGORIA = [
    ("alguien entró a mi cuenta sin permiso, no fui yo", Categoria.SEGURIDAD),
    ("no hay wifi en toda la oficina", Categoria.REDES),
    ("mi computador no enciende desde esta mañana", Categoria.INFRAESTRUCTURA),
    ("no tengo acceso a la carpeta compartida de ventas", Categoria.PERMISOS),
    ("olvidé mi contraseña y necesito cambiarla", Categoria.CUENTAS_CONTRASENAS),
    ("el programa de facturación se cierra solo", Categoria.SOFTWARE),
    ("quisiera saber si puedo pedir vacaciones la próxima semana", Categoria.OTROS),
]


def test_categorias_individuales():
    print("\n--- Prueba 1: cada categoria se detecta por separado ---")
    todas_correctas = True

    for texto, categoria_esperada in CASOS_UNA_SOLA_CATEGORIA:
        resultado = ClasificadorTickets.clasificar(texto)
        if resultado != categoria_esperada:
            print(f"FALLO: texto '{texto}' -> se esperaba {categoria_esperada}, se obtuvo {resultado}")
            todas_correctas = False

    if todas_correctas:
        print(f"OK: las {len(CASOS_UNA_SOLA_CATEGORIA)} categorias se detectaron correctamente")


def test_ambiguedad_permisos_gana_sobre_cuentas():
    print("\n--- Prueba 2: ambiguedad Permisos vs Cuentas (Permisos debe ganar) ---")
    texto = "no puedo entrar a mi cuenta, dice contraseña incorrecta"
    resultado = ClasificadorTickets.clasificar(texto)

    if resultado != Categoria.PERMISOS:
        print(f"FALLO: se esperaba PERMISOS por el orden de criticidad, se obtuvo {resultado}")
        return

    print("OK: el orden de criticidad se respeta en el caso ambiguo (Permisos gana sobre Cuentas)")


def test_mayusculas_no_afectan_la_clasificacion():
    print("\n--- Prueba 3: mayusculas en el texto no deben afectar la clasificacion ---")
    resultado = ClasificadorTickets.clasificar("NO HAY WIFI EN LA OFICINA")

    if resultado != Categoria.REDES:
        print(f"FALLO: se esperaba REDES sin importar mayusculas, se obtuvo {resultado}")
        return

    print("OK: la clasificacion no distingue mayusculas de minusculas")


if __name__ == "__main__":
    test_categorias_individuales()
    test_ambiguedad_permisos_gana_sobre_cuentas()
    test_mayusculas_no_afectan_la_clasificacion()