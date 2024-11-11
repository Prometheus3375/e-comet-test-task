from logging import Formatter, StreamHandler, getLogger
from threading import RLock

_called = False
_lock = RLock()


def init_logging(
        formatter: Formatter,
        /,
        *,
        level: str = 'INFO',
        use_new_handler: bool = True
        ) -> None:
    """
    Initializes Python logging with the specified level and formatter.
    If called more than once, this function is no-op.

    :param formatter: The formatter for log records.
    :param level: The level of logging. Defaults to ``INFO``.
    :param use_new_handler: If ``True``, then creates a new logging handler.
      Otherwise, uses the first handler of the root logger.
    """
    with _lock:
        global _called
        if _called: return

        logger = getLogger()
        logger.setLevel(level)

        if use_new_handler:
            handler = StreamHandler()
            logger.addHandler(handler)
        else:
            handler = logger.handlers[0]

        handler.setFormatter(formatter)

        _called = True


__all__ = 'init_logging',
