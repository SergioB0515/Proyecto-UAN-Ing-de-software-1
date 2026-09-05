"""
Pruebas de ClasificadorTickets.clasificar()

Que verifica:
1. Que cada categoria se detecta correctamente con un texto claro y sin ambiguedad.
2. Que un texto sin ninguna palabra clave conocida cae en OTROS.
3. El caso de ambiguedad Permisos vs Cuentas_contrasenas: por el orden de
   criticidad definido, Permisos debe ganar siempre, incluso si el texto
   menciona "contraseña" explicitamente.

No depende de la base de datos ni del app_context: son funciones puras.
"""
import pytest

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


@pytest.mark.parametrize("texto, categoria_esperada", CASOS_UNA_SOLA_CATEGORIA)
def test_categorias_individuales(texto, categoria_esperada):
    resultado = ClasificadorTickets.clasificar(texto)
    assert resultado == categoria_esperada, (
        f"texto '{texto}' -> se esperaba {categoria_esperada}, se obtuvo {resultado}"
    )


def test_ambiguedad_permisos_gana_sobre_cuentas():
    texto = "no puedo entrar a mi cuenta, dice contraseña incorrecta"
    resultado = ClasificadorTickets.clasificar(texto)
    assert resultado == Categoria.PERMISOS, (
        f"se esperaba PERMISOS por el orden de criticidad, se obtuvo {resultado}"
    )


def test_mayusculas_no_afectan_la_clasificacion():
    resultado = ClasificadorTickets.clasificar("NO HAY WIFI EN LA OFICINA")
    assert resultado == Categoria.REDES, (
        f"se esperaba REDES sin importar mayusculas, se obtuvo {resultado}"
    )
