"""Basic "make dealing with Qt layout objects easier" module."""

from PySide6 import QtWidgets


def is_widget_in_layout(widget: QtWidgets.QWidget, layout: QtWidgets.QLayout) -> bool:
    """Check if a widget is already in the given layout.

    Args:
        widget: Some Qt object to check for.
        layout: The container to check within.

    Returns:
        If ``widget`` is in ``layout``, return ``True``.

    """
    for row in range(layout.count()):
        item = layout.itemAt(row)

        if item and item.widget() == widget:
            return True

    return False
