from threading import RLock

_called = False
_lock = RLock()


def init_logging(
        *,
        msgformat: str = '%(asctime)s [%(name)s] %(levelname)s    %(message)s',
        dateformat: str = '%Y-%m-%d %H:%M:%S',
        level: str = 'INFO',
        ) -> None:
    """
    Initializes Python logging with the specified formats and level.
    If called more than once, this function is no-op.
    """
    with _lock:
        global _called
        if _called: return

        from logging import Formatter, StreamHandler, getLogger

        handler = StreamHandler()
        handler.setFormatter(Formatter(msgformat, dateformat))

        logger_ = getLogger()
        logger_.setLevel(level)
        logger_.addHandler(handler)
        _called = True


__all__ = 'init_logging',
