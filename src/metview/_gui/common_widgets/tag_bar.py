"""A module containing a custom widget for writing and saving tags.

The :class:`TagBar` class, acts like the "component" widget in Jira. Written
text gets changed from raw text into a button. Clicking the button removes the
tag, if you don't want that tag anymore.

"""

import logging
import operator
import typing

from PySide6 import QtCore, QtGui, QtWidgets

from ..common import layouter
from . import context_manager

_DELIMITER = ","
_COMMON_HEIGHT = 4
_LOGGER = logging.getLogger(__name__)

_EAST = QtWidgets.QTabWidget.TabPosition.East
_WEST = QtWidgets.QTabWidget.TabPosition.West

T = typing.TypeVar("T")


class _ClickLabel(QtWidgets.QLabel):
    """A basic QLabel that tracks left clicks."""

    left_clicked = QtCore.Signal()

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None):
        """Initialize this instance.

        Args:
            text:
                The text to add for this instance, if any.
            parent:
                An object which, if provided, holds a reference to this instance.

        """
        super(_ClickLabel, self).__init__(text=text, parent=parent)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """If the user left-clicks this widget, fire a signal.

        Args:
            event:
                The event which must be processed by this method.

        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.left_clicked.emit()

            return

        super(_ClickLabel, self).mousePressEvent(event)


class _TagButton(QtWidgets.QWidget):
    """A simple button which has an inner side button. Clicking the button fires a signal.

    Attributes:
        side_button_requested:
            Fire a signal whenever the user presses the side button.

    """

    side_button_requested = QtCore.Signal(str)

    def __init__(
        self,
        text: str,
        button_text: str = "x",
        parent: QtWidgets.QWidget | None = None,
    ):
        """Display ``text`` + an clickable side button.

        Args:
            text:
                The word / phrase to show to the user, for this instance.
            button_text:
                A label for the side button. Usually, you'll want to keep the
                default value.
            parent:
                An object which, if provided, holds a reference to this instance.

        """
        super(_TagButton, self).__init__(parent=parent)

        main_layout = QtWidgets.QHBoxLayout()
        self.setLayout(main_layout)

        self._deleter_button = _ClickLabel(button_text)

        self._tag = QtWidgets.QFrame()
        tag_layout = QtWidgets.QHBoxLayout()
        self._tag.setLayout(tag_layout)

        self._label = QtWidgets.QLabel(text)

        tag_layout.addWidget(self._label)
        tag_layout.addItem(_create_horizontal_spacer(2))
        tag_layout.addWidget(self._deleter_button)
        main_layout.addWidget(self._tag)

        self._initialize_default_settings()
        self._initialize_interactive_settings()

    def _initialize_default_settings(self) -> None:
        """Set the appearance of all child widgets."""
        palette = self.palette()
        background = palette.color(QtGui.QPalette.ColorRole.Window)
        self._tag.setStyleSheet(
            """
            .QFrame {
                background-color: %s;
                border: 1px solid rgb(192, 192, 192);
                border-radius: %spx;  /* This property also affects the widget's height */
            }
            """
            % (background.name(), _COMMON_HEIGHT)
        )
        policy = QtWidgets.QSizePolicy.Policy
        self._tag.setSizePolicy(policy.Maximum, policy.Preferred)

        self._deleter_button.setToolTip("Press me to delete the tag")
        self._deleter_button.setSizePolicy(policy.Fixed, policy.Fixed)

        spacing = 5
        _check_none(self._tag.layout()).setContentsMargins(
            spacing,
            spacing,
            spacing,
            spacing,
        )

        layout = _check_none(self.layout())
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label.setObjectName("_label")
        self._tag.setObjectName("_tag")
        self._deleter_button.setObjectName("_deleter_button")

    def _initialize_interactive_settings(self) -> None:
        """Set up the automatic behavior of this instance."""
        self._deleter_button.left_clicked.connect(self._emit_delete_request)

    def _emit_delete_request(self) -> None:
        """Tell Qt about the tag that was just pressed."""
        self.side_button_requested.emit(self.get_tag_text())

    def get_tag_text(self) -> str:
        """str: Get the display text of this instance."""
        return self._label.text()

    def set_font(self, font: QtGui.QFont) -> None:
        """Set the bold / italics / etc according to ``font``.

        Args:
            font: The text description to apply.

        """
        self._label.setFont(font)
        self._deleter_button.setFont(font)

    def __eq__(self, other: typing.Any) -> bool:
        """Check if ``other`` is the same as this instance.

        Args:
            other: Some other ``_TagButton`` to check.

        Returns:
            If ``other`` is a button with the same text, return ``True``.

        """
        if not type(other) == _TagButton:
            return False

        return self.get_tag_text() == other.get_tag_text()

    def __hash__(self) -> int:
        """Get a simplified, immutable representation for this instance."""
        return hash(self.get_tag_text())


class TagBar(QtWidgets.QWidget):
    """A fancy QLineEdit that saves text as clickable buttons.

    Clicking any of the saved button deletes the button from this instance.

    This class, like the "component" widget in Jira. Written text gets changed
    from raw text into a button. Clicking the button removes the tag, if you
    don't want that tag anymore.

    References:
        https://robonobodojo.wordpress.com/2018/09/11/creating-a-tag-bar-in-pyside/

    Attributes:
        text_changed: The current, in progress user's text.
        tags_changed: The current tags on this instance.

    """

    text_changed = QtCore.Signal(str)
    tags_changed = QtCore.Signal(list)

    def __init__(
        self,
        tags: typing.Sequence[str] | None = None,
        tag_side: QtWidgets.QTabWidget.TabPosition = _WEST,
        delimiter: str = _DELIMITER,
        line_edit: QtWidgets.QLineEdit | None = None,
        allow_duplicates: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ):
        """Store tags in this instance and create the default widget display.

        Args:
            tags:
                The tags to initially display.
            tag_side:
                A direction where new tags will be displayed from.
            delimiter:
                If the user writes more than one tag at a time, this delimiter
                is used to split the text into multiple tags and adds each tag,
                at once.
            line_edit:
                The widget used to input tags. If no widget is given, a simple
                QLineEdit is used instead. This parameter exists to extend the
                functionality of the tags widget.
            allow_duplicates:
                If ``True``, the same tag can be added more than once.
            parent:
                An object which, if provided, holds a reference to this instance.

        """
        super(TagBar, self).__init__(parent=parent)

        self._delimiter = delimiter

        if tags is not None:
            self._tags = list(tags)
        else:
            self._tags = []

        self.setLayout(QtWidgets.QHBoxLayout())

        self._allow_duplicates = allow_duplicates
        self._tags_container = QtWidgets.QHBoxLayout()
        self._line_edit = line_edit or QtWidgets.QLineEdit()

        layout = _check_none(self.layout())

        if tag_side == _EAST:
            layout.addLayout(self._tags_container)
            layout.addWidget(self._line_edit)
        elif tag_side == _WEST:
            layout.addWidget(self._line_edit)
            layout.addLayout(self._tags_container)
        else:
            raise ValueError(
                'Side "{tag_side}" is not allowed. Options were, "{options}".'.format(
                    tag_side=tag_side,
                    options={_EAST, _WEST},
                )
            )

        self._initialize_default_settings()
        self._initialize_interactive_settings()

    def _initialize_default_settings(self) -> None:
        """Set the appearance of all child widgets."""
        self._line_edit.setPlaceholderText("tag-name-here")
        self.set_tool_tip("Type here to add new tags")

        layout = _check_none(self.layout())
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._line_edit.setStyleSheet(
            """\
            QLineEdit {
                padding-top: %spx;
                padding-bottom: %spx;
            }
            """
            % (_COMMON_HEIGHT, _COMMON_HEIGHT)
        )

        self._tags_container.setContentsMargins(0, 0, 0, 0)
        self._tags_container.setSpacing(0)

        for widget, name in [
            (self._tags_container, "_tags_container"),
            (self._line_edit, "_line_edit"),
        ]:
            widget.setObjectName(name)

    def _initialize_interactive_settings(self) -> None:
        """Set up the automatic behavior of this instance."""
        self._line_edit.editingFinished.connect(self._generate_tags)
        self._line_edit.textChanged.connect(self.text_changed.emit)

    def _add_tag(self, text: str) -> None:
        """Add ``text`` as a new tag button.

        Args:
            text: The display text / phrase to add as a new tag.

        """
        tag = _TagButton(text)

        if not self._allow_duplicates and layouter.is_widget_in_layout(
            tag, self._tags_container
        ):
            _LOGGER.debug('Skipped adding "%s" duplicate tag.', tag)

            return

        tag.side_button_requested.connect(self._delete_tag)
        self._tags_container.addWidget(tag)

    def _clear_widget_tags(self) -> None:
        """Delete all tags on this instance.

        Important:
            This operation should not fire any signals.

        """
        for index in reversed(range(self._tags_container.count())):
            self._tags_container.itemAt(index).widget().setParent(None)

    def _delete_tag(self, name: str) -> None:
        """Delete all instances of ``name`` from this widget.

        Args:
            name: The name which, we assume, matches a tag name.

        """
        self._tags.remove(name)
        self._refresh()
        self.tags_changed.emit(self._tags)

    def _generate_tags(self) -> None:
        """Take any user-written tags and convert them into tag buttons."""
        text = self._line_edit.text()

        if not text:
            return

        new_tags = []

        for token in text.split(self._delimiter):
            token = token.strip()

            if token:
                new_tags.append(token)

        with context_manager.block_signals([self._line_edit]):
            self._line_edit.setText("")

        self._tags.extend(new_tags)

        self._refresh()

    def _refresh(self) -> None:
        """Re-create the tags on this widget."""
        self._clear_widget_tags()

        for tag in self._tags or []:
            self._add_tag(tag)

        self._line_edit.setFocus()

    def get_tags(self) -> list[str]:
        """Get all user-saved tags. This method ignores any text in ``QLineEdit``."""
        return [widget.get_tag_text() for widget in self.iter_tag_widgets()]

    def iter_tag_widgets(self) -> typing.Generator[_TagButton, None, None]:
        """Get every tag button in this instance, if any.

        Raises:
            If any tag in this instance somehow has no widget representation.

        Yields:
            The user-registered tags.

        """
        for index in range(self._tags_container.count()):
            item = self._tags_container.itemAt(index)
            widget = typing.cast(_TagButton | None, item.widget())

            if not widget:
                raise RuntimeError(f'Index "{index}" has no widget.')

            yield widget

    def layout(self) -> QtWidgets.QHBoxLayout:
        """Override the layout type so mypy will not complain about missing methods."""
        return typing.cast(QtWidgets.QHBoxLayout, super().layout())

    def set_placeholders(self, tags: typing.Iterable[str]) -> None:
        """Add ``tags`` as placeholder tags.

        Args:
            tags: The words / phrases to add into this instance.

        """
        self._line_edit.setPlaceholderText(", ".join(tags))

    def set_tags(self, tags: typing.Iterable[str]) -> None:
        """Create new tag buttons, using ``tags``.

        Args:
            tags:
                The tags to set onto this instance. If no tags are given, this
                widget clears all tags.

        """
        if tags is not None:
            self._tags = list(tags)
        else:
            self._tags = []

        self._refresh()
        self.tags_changed.emit(self._tags)

    def set_tool_tip(self, text: str) -> None:
        """Add a description of this instance which can be displayed on-hover.

        Args:
            text: The description to add.

        """
        self._line_edit.setToolTip(text)


def _create_horizontal_spacer(width: int) -> QtWidgets.QSpacerItem:
    """Make a spacer with `width` horizontal space."""
    return QtWidgets.QSpacerItem(
        width,
        0,
        QtWidgets.QSizePolicy.Policy.Fixed,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )


def _check_none(item: T | None) -> T:
    """Check if ``item`` is defined.

    Basically this is just a mypy hack.

    Args:
        item: Some object.

    Raises:
        RuntimeError: If ``item`` is not defined.

    Returns:
        The original ``item``.

    """
    if item is not None:
        return item

    raise RuntimeError(f'Item "{item}" was none. Cannot continue.')
