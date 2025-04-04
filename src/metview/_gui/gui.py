# coding: utf-8

"""The main ``show-gui`` widget. It can be embedded or a standalone window."""

import functools
import math
import time
import typing

from PySide6 import QtCore, QtGui, QtWidgets

from .._core import constant
from .._restapi import met_get
from .common import common_qt
from .common_widgets import line_edit_extended, tag_bar
from .models import art_model
from .utilities import threader
from .utility_widgets import details_pane

_INDEX_TYPES = QtCore.QModelIndex | QtCore.QPersistentModelIndex
T = typing.TypeVar("T")


class _CropProxy(QtCore.QIdentityProxyModel):
    """Prevent a source model from showing more than a certain number of Artworks.

    Important:
        XXX: The take-home test mentions cropping any results so we do that here.
        Using this proxy, the table will never exceed 80 results at at time.

    """

    def rowCount(self, parent: _INDEX_TYPES = QtCore.QModelIndex()) -> int:
        """Force the number of rows to be 80-or-less.

        Args:
            parent: The source / proxy Qt location to search within for children.

        Returns:
            All found children, if any.

        """
        return min(80, super().rowCount(parent))


class _MetThrottler:
    """A class that prevents too many queries to the Met REST API.

    Important:
        We throttle our queries just in case because The Met asks
        to keep queries < 80 per second.

    References:
        https://metmuseum.github.io

        At this time, we do not require API users to register or obtain an API key to
        use the service. Please limit request rate to 80 requests per second.

    """

    def __init__(self) -> None:
        """Keep track of variables so we can do throttling later."""
        super().__init__()

        self._current_time = time.time()
        self._timeframe = 1
        self._maximum = 80
        self._counter = 0

    def _is_timeframe_okay(self) -> bool:
        """Check if the user is > 1 second."""
        return self._get_elapsed_time() > self._timeframe

    def _get_elapsed_time(self) -> float:
        """Figure out how much time, 0-to-1 second, has passed."""
        return time.time() - self._current_time

    def needs_to_wait(self) -> bool:
        """Check if the user has queried The Met too much and needs to wait."""
        return self._counter > self._maximum and not self._is_timeframe_okay()

    def increment(self) -> None:
        """Tell this instance "we queried The Met's REST API exactly 1 more time."""
        self._counter += 1

    def wait(self) -> None:
        """Stop execution until enough time has passed (< 1 second)."""
        time.sleep(1 - self._get_elapsed_time())
        self._current_time = time.time()
        self._counter = 0


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

        self._source_model: art_model.Model  # NOTE: This will be set soon
        self.set_model(model or art_model.Model())

        self._threads: list[tuple[QtCore.QThread, threader.ArtSearchWorker]] = []
        self._throttler = _MetThrottler()

        self._filterer_debouncer = QtCore.QTimer(self)

        self._initialize_default_settings()
        self._initialize_interactive_settings()

        # NOTE: We show some initial data to the user
        self._update_search(met_get.get_all_identifiers)

    def _initialize_default_settings(self) -> None:
        """Set the default appearance of child widgets."""
        common_qt.initialize_framed_label(self._no_artwork_label)
        common_qt.initialize_framed_label(self._details_no_selection_label)
        self._artwork_splitter.setHandleWidth(25)  # Arbitrary, thick value
        self._details_switcher.setCurrentWidget(self._details_no_selection_label)
        self._details_pane.setTabBarAutoHide(True)

        self._filter_line.setPlaceholderText("Example: La Grenouillère")

        self._no_artwork_label.setToolTip(
            "No artwork has been loaded yet. Once there is artwork to see, "
            "this widget will be automatically hidden "
            "and you will see a table with the data.",
        )
        self._artwork_view.horizontalHeader().setStretchLastSection(True)
        self._artwork_view.setSelectionBehavior(
            QtWidgets.QListView.SelectionBehavior.SelectRows
        )
        self._artwork_view.setSelectionMode(
            QtWidgets.QListView.SelectionMode.ExtendedSelection
        )
        self._artwork_view.verticalHeader().hide()

        self._filter_missing_image_check_box.setToolTip(
            "If enabled, only entries that have a thumbnail will be shown."
        )

        self._filter_line.setToolTip("Type the name of the Work of Art here.")

        self._details_pane.setToolTip("Information about the selected artwork.")
        self._details_no_selection_label.setToolTip(
            "If you are seeing this, you need to select some artwork. "
            "Once you do that, this widget will be replaced with the artwork details."
        )

    def _initialize_interactive_settings(self) -> None:
        """Create any click / automatic functionality for this instance."""

        def _update_if_long_enough() -> None:
            # PERF: A query with short text can take a very long time. To avoid
            # user stress, we enforce a minimum before the search shows results.
            #
            # XXX: This isn't the best way to do this but, for the purposes of
            # the assessment, this is enough, I think.
            #
            text = self._filter_line.text().strip()

            if text and len(text) < 3:
                return

            self._update_search()

        self._classications_widget.tags_changed.connect(_ignore(self._update_search))
        self._filter_missing_image_check_box.stateChanged.connect(
            _ignore(self._update_search)
        )

        # PERF: Is a user is typing quickly, to keep the GUI snappy, we wait
        # for a pause in their typing before refreshing.
        #
        self._filterer_debouncer.setInterval(200)  # NOTE: Wait 0.2 sec between refresh
        self._filterer_debouncer.setSingleShot(True)
        self._filterer_debouncer.timeout.connect(_update_if_long_enough)
        self._filter_line.textChanged.connect(self._filterer_debouncer.start)

    def _get_current_classifications(self) -> tuple[str, ...]:
        """Get all user-saved Artwork "classifications"."""
        return tuple(self._classications_widget.get_tags())

    def _update_search(
        self, caller: typing.Callable[[], list[int]] | None = None
    ) -> None:
        """Compose a search to The Met's API and get its results.

        Args:
            caller: A function that can customize how we find Artwork identifiers.

        """
        # NOTE: Cancel any in-progress searches so we can run another
        for thread, worker in self._threads:
            worker.stop()

            if thread.isRunning():
                thread.quit()

        caller = caller or functools.partial(
            met_get.search_objects,
            has_image=self._filter_missing_image_check_box.isChecked(),
            classifications=self._get_current_classifications(),
            text=self._filter_line.text(),
        )
        thread = QtCore.QThread(parent=self)
        worker = threader.ArtSearchWorker(caller)
        self._threads.append((thread, worker))
        worker.moveToThread(thread)
        worker.identifiers_found.connect(self._source_model.update_artwork_identifiers)
        thread.started.connect(worker.run)

        # PERF: To prevent DDOSing The Met accidentally, we wait.
        # See :class:`_MetThrottler` for details.
        #
        if self._throttler.needs_to_wait():
            self._throttler.wait()

        self._throttler.increment()
        thread.start()

    def set_model(self, model: art_model.Model) -> None:
        """Store and display source ``model``.

        Args:
            model: Some Met Museum-related artwork model.

        Raises:
            RuntimeError: If ``model`` could not be applied as expected due to a bug.

        """
        self._source_model = model
        cropper = _CropProxy(parent=self)
        cropper.setSourceModel(model)
        self._artwork_view.setModel(cropper)


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


def _ignore(caller: typing.Callable[[], T]) -> typing.Callable[[], T]:
    """Ignore all arguments to ``caller`` when it gets called later.

    Args:
        caller: A function that we don't want to pass arguments to.

    Returns:
        An augmented ``caller`` that ignores arguments.

    """

    @functools.wraps(caller)
    def wrapper(*_: typing.Any, **__: typing.Any) -> T:
        return caller()

    return wrapper
