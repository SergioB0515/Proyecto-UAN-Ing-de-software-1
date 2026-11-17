from sqlalchemy import create_engine, inspect, text

from app.migraciones import COLUMNAS_NUEVAS, columnas_faltantes


def test_detecta_y_agrega_columnas_faltantes(tmp_path):
    motor = create_engine(f"sqlite:///{tmp_path / 'vieja.db'}")
    with motor.begin() as c:
        c.execute(text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre VARCHAR(100))"))
        c.execute(text("CREATE TABLE comentarios (id INTEGER PRIMARY KEY, texto VARCHAR)"))
        c.execute(text("CREATE TABLE tickets (id INTEGER PRIMARY KEY, texto VARCHAR)"))
        c.execute(text("INSERT INTO usuarios (nombre) VALUES ('Ana')"))
        c.execute(text("INSERT INTO comentarios (texto) VALUES ('hola')"))
        c.execute(text("INSERT INTO tickets (texto) VALUES ('no hay red')"))

    faltantes = columnas_faltantes(motor)
    assert {(t, col) for t, col, _ in faltantes} == {(t, col) for t, col, _ in COLUMNAS_NUEVAS}

    for tabla, columna, tipos in faltantes:
        with motor.begin() as c:
            c.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipos['sqlite']}"))

    assert columnas_faltantes(motor) == []
    with motor.connect() as c:
        assert c.execute(text("SELECT activo FROM usuarios")).scalar() == 1
        assert c.execute(text("SELECT interno FROM comentarios")).scalar() == 0
        assert c.execute(text("SELECT notificado_sin_asignar FROM tickets")).scalar() == 0
        # Columnas del reloj de SLA en pausa y de la cobertura (3.5): un ticket
        # que ya existia tiene que quedar sin pausas y sin marca de cobertura.
        assert c.execute(text("SELECT sla_segundos_pausados FROM tickets")).scalar() == 0
        assert c.execute(text("SELECT requiere_cobertura FROM tickets")).scalar() == 0
        assert c.execute(text("SELECT sla_pausado_desde FROM tickets")).scalar() is None
    assert "ultimo_acceso" in {col["name"] for col in inspect(motor).get_columns("usuarios")}
