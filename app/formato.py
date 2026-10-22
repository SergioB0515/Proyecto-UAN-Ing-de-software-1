import re

from markupsafe import Markup, escape

_NEGRITA = re.compile(r"\*\*(.+?)\*\*")
_CURSIVA = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_CODIGO = re.compile(r"`([^`]+)`")
_ENLACE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+|/[^\s)]*)\)")


def _en_linea(texto):
    texto = str(escape(texto))
    codigos = []

    def guardar_codigo(m):
        codigos.append(m.group(1))
        return f"\x00{len(codigos) - 1}\x00"

    texto = _CODIGO.sub(guardar_codigo, texto)
    texto = _NEGRITA.sub(r"<strong>\1</strong>", texto)
    texto = _CURSIVA.sub(r"<em>\1</em>", texto)
    texto = _ENLACE.sub(r'<a href="\2" rel="noopener noreferrer" target="_blank">\1</a>', texto)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codigos[int(m.group(1))]}</code>", texto)


def markdown_seguro(texto):
    if not texto:
        return Markup("")
    html = []
    lista = None
    parrafo = []
    bloque_codigo = None

    def cerrar_parrafo():
        if parrafo:
            html.append("<p>" + "<br>".join(_en_linea(l) for l in parrafo) + "</p>")
            parrafo.clear()

    def cerrar_lista():
        nonlocal lista
        if lista:
            etiqueta, items = lista
            html.append(f"<{etiqueta}>" + "".join(f"<li>{_en_linea(i)}</li>" for i in items) + f"</{etiqueta}>")
            lista = None

    for linea in texto.replace("\r\n", "\n").split("\n"):
        if linea.strip().startswith("```"):
            if bloque_codigo is None:
                cerrar_parrafo()
                cerrar_lista()
                bloque_codigo = []
            else:
                html.append("<pre><code>" + str(escape("\n".join(bloque_codigo))) + "</code></pre>")
                bloque_codigo = None
            continue
        if bloque_codigo is not None:
            bloque_codigo.append(linea)
            continue

        limpia = linea.strip()
        titulo = re.match(r"^(#{1,3})\s+(.*)$", limpia)
        vineta = re.match(r"^[-*]\s+(.*)$", limpia)
        numerada = re.match(r"^\d+[.)]\s+(.*)$", limpia)
        cita = re.match(r"^>\s?(.*)$", limpia)

        if not limpia:
            cerrar_parrafo()
            cerrar_lista()
        elif titulo:
            cerrar_parrafo()
            cerrar_lista()
            nivel = min(len(titulo.group(1)) + 2, 5)
            html.append(f"<h{nivel}>{_en_linea(titulo.group(2))}</h{nivel}>")
        elif vineta or numerada:
            cerrar_parrafo()
            etiqueta = "ul" if vineta else "ol"
            if lista is None or lista[0] != etiqueta:
                cerrar_lista()
                lista = (etiqueta, [])
            lista[1].append((vineta or numerada).group(1))
        elif cita:
            cerrar_parrafo()
            cerrar_lista()
            html.append(f"<blockquote>{_en_linea(cita.group(1))}</blockquote>")
        else:
            cerrar_lista()
            parrafo.append(limpia)

    if bloque_codigo is not None:
        html.append("<pre><code>" + str(escape("\n".join(bloque_codigo))) + "</code></pre>")
    cerrar_parrafo()
    cerrar_lista()
    return Markup("\n".join(html))
