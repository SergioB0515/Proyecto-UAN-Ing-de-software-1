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
    pass
class SolicitudDuplicadaError(Exception):
    pass
class SolicitudNoEncontradaError(Exception):
    pass
class SolicitudNoPendienteError(Exception):
    pass
class AgenteDestinoInvalidoError(Exception):
    pass
class AreaDestinoInvalidaError(Exception):
    pass
class MotivoRequeridoError(Exception):
    pass
class PrioridadDestinoInvalidaError(Exception):
    pass
class ClasificacionYaConfirmadaError(Exception):
    pass