
class TransicionInvalidaError(Exception):
    pass
class AgenteYaAsignadoError(Exception):
    pass
class TicketNoEncontradoError(Exception):
    pass
class TicketNoEnProgresoError(Exception):
    pass
class ComentarioVacioError(Exception):
    pass
class NoHayTickets(Exception):
    pass
class ErrorPersistencia(Exception):
    """Se lanza cuando falla el guardado en la base de datos (commit) y ya se hizo rollback."""
    pass
