# coding: utf-8

"""The main ``show-gui`` widget. It can be embedded or a standalone window."""

import functools
import logging
import math
import time
import typing

from PySide6 import QtCore, QtGui, QtWidgets

from .._core import constant
from .._restapi import met_get, met_get_type
from .common import common_qt, iterbot, qt_constant
from .common_widgets import line_edit_extended, tag_bar
from .models import art_model, model_type
from .utilities import threader
from .utility_widgets import collapsible, details_pane

_INDEX_TYPES = QtCore.QModelIndex | QtCore.QPersistentModelIndex
T = typing.TypeVar("T")
_DISPLAY_ROLE = QtCore.Qt.ItemDataRole.DisplayRole
_LOGGER = logging.getLogger(__name__)


class _ArtworkLoadStatistics(typing.NamedTuple):
    """Describe which Artworks have data vs the ones shown.

    Attributes:
        total: All of the Artwork that a user might have seen.
        visible: The number of rows shown.

    """

    total: int
    visible: int


class _ArtworkSortFilterProxy(QtCore.QSortFilterProxyModel):
    """Sort and filter artwork based on the user's input."""

    def __init__(
        self,
        filter_functions: (
            typing.Sequence[typing.Callable[[QtCore.QModelIndex], bool]] | None
        ) = None,
        parent: QtCore.QObject | None = None,
    ):
        """Store functions which may be used to filter by, later.

        Args:
            filter_functions:
                Any functions used to filter by. If no functions are given, no
                indices will be filtered. If a function is given and returns
                True, the index is filtered. If the function returns False,
                it is skipped. If no function returns True, the index is shown.
            parent:
                The Qt-based object to assign this instance underneath.

        """
        super().__init__(parent=parent)

        self._filter_functions = filter_functions or []

    def filterAcceptsRow(self, source_row: int, source_parent: _INDEX_TYPES) -> bool:
        """Filter the row ``source_row`` in ``source_parent``, if needed.

        Args:
            source_row:
                A 0-based index to check within ``source_parent`` for filtering.
                This row is relative to ``source_parent``.
            source_parent:
                The anchor / reference point to search for an index row.

        Returns:
            bool: If False is returned, the row is hidden. If True, it is shown.

        """
        model = self.sourceModel()
        index = model.index(source_row, qt_constant.ANY_COLUMN, source_parent)

        for function in self._filter_functions:
            if function(index):
                return False

        return True

    def lessThan(self, left: _INDEX_TYPES, right: _INDEX_TYPES) -> bool:
        """Check if ``left`` actually comes before ``right`` when both are sorted.

        Args:
            left: Some Qt locatino to check.
            right: Another Qt locatino to check.

        Returns:
            If ``left`` must come before ``right``, return ``True``. If it doesn't
            matter or ``left`` goes after ``right``, return ``False``.

        """

        def _get_default_text(index: _INDEX_TYPES) -> str:
            return index.data(_DISPLAY_ROLE) or ""

        column = left.column()

        if column == art_model.Column.datetime:
            left_datetime = typing.cast(
                met_get_type.Datetime | None,
                left.data(art_model.Model.data_role),
            )

            if not left_datetime:
                return False

            right_datetime = typing.cast(
                met_get_type.Datetime | None,
                right.data(art_model.Model.data_role),
            )

            if not right_datetime:
                return True

            return left_datetime < right_datetime

        return _get_default_text(left) < _get_default_text(right)


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
        self._statistics_label = QtWidgets.QLabel()

        main_layout.addWidget(self._widget)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self._statistics_label)
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
        self._widget.statistics_changed.connect(self._update_statistics)

    def _update_statistics(self, statistics: _ArtworkLoadStatistics) -> None:
        self._statistics_label.setText(
            f"Visible: {statistics.visible} | Total: {statistics.total}"
        )


class Widget(QtWidgets.QWidget):
    """The main ``show-gui`` widget. It can be embedded or a standalone window.

    Attributes:
        statistics_changed:
            Any time the view changes in a way that impacts the overall Artwork
            statistics (e.g. the user launches a new search.)

    """

    statistics_changed = QtCore.Signal(_ArtworkLoadStatistics)

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
        self._filter_label = QtWidgets.QLabel("Filter-By Title:")
        self._filter_line = QtWidgets.QLineEdit()
        self._filter_button = QtWidgets.QPushButton("Search")
        self._filter_details = QtWidgets.QPushButton("Details")
        self._filter_missing_image_check_box = QtWidgets.QCheckBox("Has Images Only")

        self._group_filter_widget = collapsible.SectionHider(title="More Filters")
        self._classications_label = QtWidgets.QLabel("Classifications")
        self._classication_widget = _get_classification_qlineedit()

        # NOTE: The lower artwork + details widgets
        #
        # +-------+-------------------------+
        # | art_a | name: art_a             |
        # | art_b | artist: Some Person Jr. |
        # +-------+-------------------------+
        #
        self._no_artwork_label = QtWidgets.QLabel("No artwork loaded yet. Please wait!")
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
        self._artwork_switcher.addWidget(self._no_artwork_label)
        self._artwork_switcher.addWidget(self._artwork_splitter)
        self._artwork_splitter.addWidget(self._artwork_view)
        self._artwork_splitter.addWidget(self._details_switcher)

        top = QtWidgets.QGridLayout()
        top.addWidget(self._filter_label, 0, 0)
        top.addWidget(self._filter_line, 0, 1)
        top.addWidget(self._filter_button, 0, 2)
        main_layout.addLayout(top)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(self._filter_missing_image_check_box, 0, 0, 1, -1)
        layout.addWidget(self._classications_label, 1, 0, 1, 1)
        layout.addWidget(self._classication_widget, 1, 1, 1, -1)
        self._group_filter_widget.set_content_layout(layout)
        main_layout.addWidget(self._group_filter_widget)

        main_layout.addWidget(self._artwork_switcher)

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
        self._classication_widget.setPlaceholderText(
            "Example: Books, Musical Instruments Prints"
        )

        self._details_pane.setToolTip("Information about the selected artwork.")
        self._details_no_selection_label.setToolTip(
            "If you are seeing this, you need to select some artwork. "
            "Once you do that, this widget will be replaced with the artwork details."
        )

    def _initialize_interactive_settings(self) -> None:
        """Create any click / automatic functionality for this instance."""
        self._filter_missing_image_check_box.stateChanged.connect(
            _ignore(self._update_search)
        )

        # PERF: Is a user is typing quickly, to keep the GUI snappy, we wait
        # for a pause in their typing before refreshing.
        #
        self._filterer_debouncer.setInterval(200)  # NOTE: Wait 0.2 sec between refresh
        self._filterer_debouncer.setSingleShot(True)
        self._filterer_debouncer.timeout.connect(self._update_search)
        self._filter_button.clicked.connect(self._filterer_debouncer.start)
        self._filter_line.returnPressed.connect(self._filterer_debouncer.start)

    def _get_current_artworks(self) -> list[QtCore.QModelIndex]:
        """Get the user's current artwork selection, if any.

        Raises:
            RuntimeError: If any selected rows somehow did not find artwork.

        Returns:
            If the current user artwork selection.

        """
        model = self._artwork_view.selectionModel()

        if not model:
            raise RuntimeError(
                "Artwork view has no selection model. This is a bug, please fix!"
            )

        invalids: list[typing.Any] = []
        output: list[QtCore.QModelIndex] = []
        selected = model.selectedIndexes()

        for index in iterbot.iter_unique_rows(selected):
            data = index.data(art_model.Model.artwork_role)

            if not isinstance(data, model_type.Artwork):
                invalids.append(data)

            output.append(index)

        if invalids:
            raise RuntimeError(f'Got unknown "{invalids}" data. Expected arkwork!')

        # IMPORTANT: ``output`` contains proxy indices which could cause the GUI to seg
        # fault if the user messes with filters so we get the real source index before
        # returning.
        #
        proxy = self._artwork_view.model()
        source = iterbot.get_lowest_source(proxy)

        return [iterbot.map_to_source_recursively(index, source) for index in output]

    def _get_current_classification(self) -> str:
        """Get all user-saved Artwork "classification"."""
        return self._classication_widget.text()

    def _emit_statistics(self) -> None:
        """Gather information about the Artwork that the user can see."""
        parent = QtCore.QModelIndex()
        top = self._artwork_view.model()
        visible = top.rowCount(parent)
        total = self._source_model.rowCount(parent)
        statistics = _ArtworkLoadStatistics(total=total, visible=visible)
        self.statistics_changed.emit(statistics)

    def _update_details_pane(self) -> None:
        """Show or hide the details pane if the user has selected some artwork."""
        if artworks := self._get_current_artworks():
            self._details_pane.set_current_artworks(artworks)
            self._details_switcher.setCurrentWidget(self._details_pane)
        else:
            self._details_switcher.setCurrentWidget(self._details_no_selection_label)

    def _update_main_switcher(self) -> None:
        """Show the artwork table if there is any data to show."""
        if not self._source_model.rowCount(QtCore.QModelIndex()):
            self._artwork_switcher.setCurrentWidget(self._no_artwork_label)
        else:
            self._artwork_switcher.setCurrentWidget(self._artwork_splitter)

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
            classification=self._get_current_classification(),
            text=self._filter_line.text(),
        )
        thread = QtCore.QThread(parent=self)
        worker = threader.ArtSearchWorker(caller)
        self._threads.append((thread, worker))
        worker.moveToThread(thread)
        worker.identifiers_found.connect(self._source_model.update_artwork_identifiers)
        worker.identifiers_found.connect(self._update_main_switcher)
        worker.identifiers_found.connect(self._emit_statistics)
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

        def _has_image(index: QtCore.QModelIndex) -> bool:
            if not self._filter_missing_image_check_box.isChecked():
                return False  # Do not filter (show the ``index``)

            source = iterbot.get_lowest_source(index.model())
            source_index = iterbot.map_to_source_recursively(index, source)
            thumbnail_index = source_index.siblingAtColumn(art_model.Column.thumbnail)
            thumbnail: str | None = None

            if not thumbnail_index.isValid():
                _LOGGER.error(
                    'Index "%s" has no thumbnail. Can\'t continue. '
                    "This should never happen and it's a bug, please fix!",
                    source_index,
                )

                return False

            thumbnail = typing.cast(str | None, thumbnail_index.data(_DISPLAY_ROLE))

            if thumbnail:
                return False  # Do not filter (show the ``index``)

            return True  # No thumbnail was found. Filter the index out.

        def _by_classification(index: QtCore.QModelIndex) -> bool:
            classification_index = index.siblingAtColumn(art_model.Column.classification)

            if not classification_index.isValid():
                _LOGGER.warning('Index "%s" has no classification index.', index)

                return False  # Do not filter (show the ``index``)

            text = self._classication_widget.text().strip()

            if not text:
                # NOTE: The user is not filtering by-name

                return False  # Do not filter (show the ``index``)

            classification = typing.cast(str, classification_index.data(_DISPLAY_ROLE))

            return text.lower() not in classification.lower()

        def _by_name(index: QtCore.QModelIndex) -> bool:
            title_index = index.siblingAtColumn(art_model.Column.title)

            if not title_index.isValid():
                _LOGGER.warning('Index "%s" has no title index.', index)

                return False  # Do not filter (show the ``index``)

            text = self._filter_line.text().strip()

            if not text:
                # NOTE: The user is not filtering by-name

                return False  # Do not filter (show the ``index``)

            title = typing.cast(str, title_index.data(_DISPLAY_ROLE))

            return text.lower() not in title.lower()

        self._source_model = model
        cropper = _CropProxy(parent=self)
        cropper.setSourceModel(model)
        sorter = _ArtworkSortFilterProxy(
            filter_functions=[_by_name, _by_classification, _has_image],
            parent=self,
        )
        sorter.setSourceModel(cropper)
        self._artwork_view.setModel(sorter)

        self._artwork_view.setSortingEnabled(True)
        self._artwork_view.sortByColumn(
            art_model.Column.title, QtCore.Qt.SortOrder.AscendingOrder
        )

        selection_model = self._artwork_view.selectionModel()

        if not selection_model:
            raise RuntimeError(
                "Artwork view has no selection model. This is a bug, please fix!"
            )

        selection_model.selectionChanged.connect(self._update_details_pane)


def _get_classification_qlineedit() -> line_edit_extended.CompleterLineEdit:
    """Get a QLineEdit that auto-completes Artwork classification text."""
    widget = line_edit_extended.CompleterLineEdit()

    # XXX: In the future it might be fun to auto-generate the list but for
    # the sake of simplicity, let's hard-code it. It's not like classification
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
