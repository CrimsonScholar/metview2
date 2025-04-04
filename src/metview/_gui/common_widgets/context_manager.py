"""Any generic, useful contexts for Qt."""

import contextlib
import functools
import typing

from PySide6 import QtCore, QtWidgets


@contextlib.contextmanager
def block_signals(
    widgets: typing.Sequence[QtWidgets.QWidget], block: bool = True
) -> typing.Generator[None, None, None]:
    """Temporarily block / unblock all ``widgets``.

    Blocked widgets will not fire signals and vice versa.

    Example:
        >>> with block_signals([button], block=True):
        ...     button.clicked.emit()  # Will do nothing

        >>> button.clicked.emit()  # Will fire signals

    Note:
        If you want to block only some signals and not all signals of
        ``widgets``, see :func:`block_callbacks`.

    Args:
        widgets:
            The object to stop / start firing signals.
        block:
            If True, no widget in `widgets` will fire signals as long as this
            context has no exited. If False, blocked widgets will start firing
            signals, instead.

    Yields:
        A context which has widgets blocked / unblocked.

    """
    signals = [(widget, widget.signalsBlocked()) for widget in widgets]

    for widget in widgets:
        widget.blockSignals(block)

    try:
        yield
    finally:
        for widget, state in signals:
            widget.blockSignals(state)
