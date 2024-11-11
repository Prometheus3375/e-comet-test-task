from logging import Formatter, StreamHandler, getLogger
from threading import RLock

_called = False
_lock = RLock()
_default_formatter = Formatter(
    '%(asctime)s [%(name)s] %(levelname)s    %(message)s',
    '%Y-%m-%d %H:%M:%S',
    )


def init_logging(
        *,
        level: str = 'INFO',
        formatter: Formatter = _default_formatter,
        use_new_handler: bool = True,
        ) -> None:
    """
    Initializes Python logging with the specified level and formatter.
    If called more than once, this function is no-op.

    :param level: The level of logging. Defaults to ``INFO``.
    :param formatter: The formatter for log records.
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
