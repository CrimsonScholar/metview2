"""Basic Qt QLineEdit classies."""

from PySide6 import QtCore, QtGui, QtWidgets


class CompleterLineEdit(QtWidgets.QLineEdit):
    """Show the completer when the line edit gains focus."""

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        """Show the completer when the line edit gains focus."""
        super().focusInEvent(event)

        self.completer().complete()
