import pytest

from app import notificaciones_i18n as notif


def test_render_constante_conocida_sin_locale():
    resultado = notif.render(notif.CERRADO, 42)
    assert resultado == "Tu ticket #42 fue cerrado", (
        f"se esperaba la plantilla CERRADO interpolada con el id real, se obtuvo '{resultado}'"
    )


def test_render_constante_conocida_locale_es_explicito():
    resultado = notif.render(notif.CERRADO, 42, locale="es")
    assert resultado == "Tu ticket #42 fue cerrado", (
        f"locale='es' explicito deberia dar el mismo resultado que sin locale, se obtuvo '{resultado}'"
    )


def test_render_traduce_a_ingles():
    resultado = notif.render(notif.CERRADO, 42, locale="en")
    assert resultado == "Your ticket #42 was closed", (
        f"se esperaba la traduccion real en ingles interpolada, se obtuvo '{resultado}'"
    )


def test_render_traduce_a_ingles_otra_plantilla():
    resultado = notif.render(notif.TRANSFERENCIA_NUEVA, 7, locale="en")
    assert resultado == "New transfer request for ticket #7", (
        f"se esperaba la traduccion real en ingles interpolada, se obtuvo '{resultado}'"
    )


def test_render_mismo_ticket_id_distinto_idioma_da_textos_distintos():
    en_espanol = notif.render(notif.CERRADO, 5, locale="es")
    en_ingles = notif.render(notif.CERRADO, 5, locale="en")

    assert en_espanol != en_ingles, (
        "se esperaban textos distintos entre 'es' y 'en', pero salieron iguales -- "
        "la traduccion no esta aplicando el locale solicitado"
    )
    assert "5" in en_espanol and "5" in en_ingles, (
        "el id del ticket debe aparecer en ambos idiomas"
    )


def test_render_ticket_id_none_no_truena():
    resultado = notif.render(notif.CERRADO, None)
    assert resultado == "Tu ticket # fue cerrado", (
        f"con ticket_id=None se espera que el id se sustituya por cadena vacia, se obtuvo '{resultado}'"
    )


def test_render_texto_legado_se_devuelve_tal_cual():
    texto_legado = "Este es un mensaje legado ya renderizado del ticket #99"

    resultado = notif.render(texto_legado, 99)
    assert resultado == texto_legado, (
        "un texto que no coincide con ninguna constante conocida debe "
        f"devolverse exactamente igual, se obtuvo '{resultado}'"
    )


def test_render_texto_legado_ignora_el_locale():
    texto_legado = "Mensaje legado sin placeholders"

    resultado_es = notif.render(texto_legado, 10, locale="es")
    resultado_en = notif.render(texto_legado, 10, locale="en")

    assert resultado_es == texto_legado
    assert resultado_en == texto_legado


def test_render_funciona_sin_peticion_http_activa():
    resultado = notif.render(notif.TRANSFERENCIA_ACEPTADA, 1, locale="en")
    assert "1" in resultado, "deberia interpolar el id sin necesitar una peticion HTTP activa"


def test_catalogo_cliente_incluye_todas_las_constantes_conocidas():
    catalogo = notif.catalogo_cliente()

    constantes_esperadas = [
        notif.CERRADO_SIN_ATENDER, notif.CERRADO,
        notif.TRANSFERENCIA_NUEVA, notif.TRANSFERENCIA_ACEPTADA, notif.TRANSFERENCIA_RECHAZADA,
        notif.ESCALAMIENTO_PENDIENTE, notif.ESCALAMIENTO_APROBADO, notif.ESCALAMIENTO_RECHAZADO,
        notif.PRIORIDAD_PENDIENTE, notif.PRIORIDAD_APROBADO, notif.PRIORIDAD_RECHAZADO,
        notif.SLA_PROXIMO_CREADOR, notif.SLA_PROXIMO_AGENTE,
        notif.SLA_VENCIDO_CREADOR, notif.SLA_VENCIDO_AGENTE,
    ]

    for constante in constantes_esperadas:
        assert constante in catalogo, f"falta la constante '{constante}' en catalogo_cliente()"


def test_catalogo_cliente_conserva_el_marcador_sin_resolver():
    catalogo = notif.catalogo_cliente()

    for plantilla_cruda, plantilla_traducida in catalogo.items():
        assert notif.MARCADOR in plantilla_traducida, (
            f"la plantilla traducida de '{plantilla_cruda}' deberia conservar "
            f"el marcador '{notif.MARCADOR}' sin resolver, se obtuvo '{plantilla_traducida}'"
        )