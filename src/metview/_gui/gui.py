# coding: utf-8

"""The main ``show-gui`` widget. It can be embedded or a standalone window."""

import math

from PySide6 import QtCore, QtGui, QtWidgets

from .._core import constant
from .._restapi import met_get
from .common_widgets import line_edit_extended, tag_bar
from .models import art_model
from .utility_widgets import details_pane


class Window(QtWidgets.QWidget):
    """A standalone version of :class:`Widget`.

    This class is not meant to be embedded into other classes via composition.
    Use :class:`Widget` instead.

    """

    def __init__(
        self,
        search_term: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Change this widget into a standalone viewer GUI.

        Args:
            search_term: Some Work of Art to initially search with, if any.
            parent: The GUI that owns this instance, if any.

        Returns:
            The created instance.

        """
        super().__init__(parent)

        main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(main_layout)

        self._close_button = QtWidgets.QPushButton("Close")
        self._widget = Widget(search_term=search_term, parent=parent)

        main_layout.addWidget(self._widget)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(self._close_button)
        main_layout.addLayout(bottom)

        self._initialize_default_settings()
        self._initialize_interactive_settings()

    def _initialize_default_settings(self) -> None:
        """Set the default appearance of child widgets."""
        self.setWindowTitle("MetViewer")
        self.setWindowIcon(QtGui.QIcon(f"{constant.QT_PREFIX}:window.svg"))
        self.setWindowFlag(QtCore.Qt.WindowType.Window)

        layout = self._widget.layout()

        if not layout:
            raise RuntimeError(
                f'Artwork widget "{self._widget}" has no layout. This is a bug.'
            )

        layout.setContentsMargins(0, 0, 0, 0)
        self._close_button.setToolTip("Press this to close this GUI window.")

        # NOTE: An arbitrary size that "looks good"
        height = 550
        golden_ratio = 1.618
        self.resize(int(math.floor(height * golden_ratio)), height)

    def _initialize_interactive_settings(self) -> None:
        """Create any click / automatic functionality for this instance."""
        self._close_button.clicked.connect(self.close)


class Widget(QtWidgets.QWidget):
    """The main ``show-gui`` widget. It can be embedded or a standalone window."""

    def __init__(
        self,
        search_term: str = "",
        model: art_model.Model | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize the child widgets for this instance.

        Args:
            search_term:
                Some Work of Art to initially search for, if any.
            model:
                A source model to display in this instance. If none is provided, an
                empty model is used instead and we query the artwork to show, ourslves.
            parent:
                The GUI that owns this instance, if any.

        """
        super().__init__(parent)

        main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(main_layout)

        # NOTE: The top widgets
        self._filter_label = QtWidgets.QLabel("Filter:")
        self._filter_line = QtWidgets.QLineEdit()
        self._filter_details = QtWidgets.QPushButton("Details")

        self._classications_label = QtWidgets.QLabel("Classifications")
        self._classications_widget = tag_bar.TagBar(
            line_edit=_get_classifications_qlineedit()
        )

        # NOTE: The lower artwork + details widgets
        #
        # +-------+-------------------------+
        # | art_a | name: art_a             |
        # | art_b | artist: Some Person Jr. |
        # +-------+-------------------------+
        #
        self._no_artwork_label = QtWidgets.QLabel(
            "No artwork loaded yet. Please wait! ~4 seconds wait time."
        )
        self._artwork_view = QtWidgets.QTableView()
        self._details_switcher = QtWidgets.QStackedWidget()
        self._details_no_selection_label = QtWidgets.QLabel(
            "This view will show art information. Please select some art on the left."
        )
        self._artwork_switcher = QtWidgets.QStackedWidget()
        self._artwork_splitter = QtWidgets.QSplitter()
        self._details_pane = details_pane.DetailsPane()
        self._details_switcher.addWidget(self._details_no_selection_label)
        self._details_switcher.addWidget(self._details_pane)
        # TODO: Add this later once we have a visual
        # self._artwork_switcher.addWidget(self._no_artwork_label)
        self._artwork_switcher.addWidget(self._artwork_splitter)
        self._artwork_splitter.addWidget(self._artwork_view)
        self._artwork_splitter.addWidget(self._details_switcher)

        top = QtWidgets.QGridLayout()
        top.addWidget(self._filter_label, 0, 0)
        top.addWidget(self._filter_line, 0, 1)
        main_layout.addLayout(top)
        main_layout.addWidget(self._artwork_switcher)

        # TODO: Add show/hide grouper, later
        self._filter_missing_image_check_box = QtWidgets.QCheckBox("Has Images Only")

        top.addWidget(self._filter_missing_image_check_box, 1, 0, 1, -1)
        top.addWidget(self._classications_label, 2, 0)
        top.addWidget(self._classications_widget, 2, 1)

        self._initialize_interactive_settings()

    def _initialize_interactive_settings(self) -> None:
        """Create any click / automatic functionality for this instance."""
        self._filter_missing_image_check_box.stateChanged.connect(self._update_search)
        # TODO: Add debouncer later
        self._filter_line.textChanged.connect(self._update_search)

    def _get_current_classifications(self) -> list[str]:
        """Get all user-saved Artwork "classifications"."""
        return self._classications_widget.get_tags()

    def _update_search(self) -> None:
        """Compose a search to The Met's API and get its results."""
        met_get.search_objects(
            has_image=self._filter_missing_image_check_box.isChecked(),
            classifications=self._get_current_classifications(),
            text=self._filter_line.text(),
        )
        raise RuntimeError("TODO: Write this")


def _get_classifications_qlineedit() -> line_edit_extended.CompleterLineEdit:
    """Get a QLineEdit that auto-completes Artwork classification text."""
    widget = line_edit_extended.CompleterLineEdit()

    # XXX: In the future it might be fun to auto-generate the list but for
    # the sake of simplicity, let's hard-code it. It's not like classifications
    # change that often anyway.
    #
    completer = QtWidgets.QCompleter(met_get.KNOWN_CLASSIFICATIONS)
    completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
    widget.setCompleter(completer)

    return widget
