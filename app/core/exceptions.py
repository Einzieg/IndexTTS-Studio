from __future__ import annotations


class StudioError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(StudioError):
    status_code = 404


class ValidationError(StudioError):
    status_code = 422


class ConflictError(StudioError):
    status_code = 409


class AuthenticationError(StudioError):
    status_code = 401


class InfrastructureError(StudioError):
    status_code = 500


class ModelUnavailableError(StudioError):
    status_code = 503


class SpeakerNotFoundError(NotFoundError):
    pass


class MissingFileError(NotFoundError):
    pass


class ScriptValidationError(ValidationError):
    pass


class OutputNameCollisionError(ConflictError):
    pass


class SynthesisError(InfrastructureError):
    pass
