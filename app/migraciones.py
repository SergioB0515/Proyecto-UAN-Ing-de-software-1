from sqlalchemy import inspect, text

from app.extensions import db

COLUMNAS_NUEVAS = [
    ("usuarios", "activo", {"sqlite": "BOOLEAN NOT NULL DEFAULT 1", "default": "BOOLEAN NOT NULL DEFAULT TRUE"}),
    ("usuarios", "ultimo_acceso", {"sqlite": "DATETIME", "default": "TIMESTAMP"}),
    ("comentarios", "interno", {"sqlite": "BOOLEAN NOT NULL DEFAULT 0", "default": "BOOLEAN NOT NULL DEFAULT FALSE"}),
]


def importar_modelos():
    from app.models import (  # noqa: F401
        usuario, ticket, comentario, log_auditoria, intento_login_fallido, ip_bloqueada,
        notificacion, transferencia, apelacion, palabra_clave, correccion_clasificacion,
        doble_factor, token_recuperacion, articulo, adjunto, respuesta_predefinida,
        seguidor_ticket, encuesta_satisfaccion, token_api,
    )


def columnas_faltantes(motor=None):
    motor = motor or db.engine
    inspector = inspect(motor)
    tablas = set(inspector.get_table_names())
    faltantes = []
    for tabla, columna, tipos in COLUMNAS_NUEVAS:
        if tabla not in tablas:
            continue
        existentes = {c["name"] for c in inspector.get_columns(tabla)}
        if columna not in existentes:
            faltantes.append((tabla, columna, tipos))
    return faltantes


def _sincronizar_enums_postgres(motor, verbose):
    from app.models import enum as enums

    clases = [
        enums.AccionAuditoria, enums.Categoria, enums.RolUsuario, enums.NivelUsuario, enums.Prioridad,
        enums.EstadoTicket, enums.EstadoSolicitudTransferencia, enums.TipoSolicitud, enums.EstadoApelacion,
    ]
    agregados = []
    with motor.connect().execution_options(isolation_level="AUTOCOMMIT") as conexion:
        for clase in clases:
            nombre_tipo = clase.__name__.lower()
            existe = conexion.execute(text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": nombre_tipo}).first()
            if not existe:
                continue
            actuales = set(conexion.execute(text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = :n"
            ), {"n": nombre_tipo}).scalars())
            for miembro in clase:
                if miembro.name not in actuales:
                    conexion.execute(text(f"ALTER TYPE {nombre_tipo} ADD VALUE IF NOT EXISTS '{miembro.name}'"))
                    agregados.append(f"{nombre_tipo}.{miembro.name}")
                    if verbose:
                        print(f"[migracion] valor de enum agregado: {nombre_tipo}.{miembro.name}")
    return agregados


def migrar(verbose=True):
    importar_modelos()
    db.create_all()
    motor = db.engine
    dialecto = "sqlite" if motor.dialect.name == "sqlite" else "default"
    aplicadas = []
    if motor.dialect.name == "postgresql":
        aplicadas.extend(_sincronizar_enums_postgres(motor, verbose))
    for tabla, columna, tipos in columnas_faltantes(motor):
        with motor.begin() as conexion:
            conexion.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipos[dialecto]}"))
        aplicadas.append(f"{tabla}.{columna}")
        if verbose:
            print(f"[migracion] columna agregada: {tabla}.{columna}")
    if verbose and not aplicadas:
        print("[migracion] el esquema ya está al día")
    return aplicadas
