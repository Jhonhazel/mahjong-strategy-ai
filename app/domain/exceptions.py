"""Explicit errors at the game, session and dataset boundaries."""


class MahjongError(Exception):
    pass


class IllegalActionError(MahjongError):
    pass


class InvalidTurnStateError(MahjongError):
    pass


class EngineInvariantError(MahjongError):
    pass


class GameNotFoundError(MahjongError):
    pass


class GameAlreadyFinishedError(MahjongError):
    pass


class SessionCapacityExceededError(MahjongError):
    pass


class ServiceShuttingDownError(MahjongError):
    pass


class DatasetDownloadError(MahjongError):
    pass


class CorruptedDatasetError(MahjongError):
    pass


class ParityVerificationError(MahjongError):
    pass
