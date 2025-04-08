"""The MVC model that interacts between The Met's API and Qt."""

import enum
import logging
import typing

from PySide6 import QtCore

from ..._restapi import met_get_type
from . import model_type

_ARTIST_TOOLTIP = "The person, group, or entity that created the art."
_DATETIME_TOOLTIP = (
    "The year or expected period when the art was made. "
    "If some art took multiple years or the time period is unknown, "
    "a date range is given."
)
_TITLE_TOOLTIP = "The name of the artwork, if any"

_INDEX_TYPES = QtCore.QModelIndex | QtCore.QPersistentModelIndex
_DISPLAY_ROLE = QtCore.Qt.ItemDataRole.DisplayRole
_TOOLTIP_ROLE = QtCore.Qt.ItemDataRole.ToolTipRole

_LOGGER = logging.getLogger(__name__)


class Column(enum.IntEnum):
    """Symbolic constants that indicate where we can access specific data."""

    title = 0
    datetime = 1
    artist = 2

    # NOTE: We don't actally display this column anywhere but we do use it to
    # ToolTipRole thumbnail information when it is needed.
    #
    thumbnail = 1000001
    classification = 1000002
    medium = 1000003


class Model(QtCore.QAbstractTableModel):
    """The MVC model that interacts between The Met's API and Qt."""

    _columns = frozenset(value.value for value in Column.__members__.values())
    artwork_role = QtCore.Qt.ItemDataRole.UserRole
    data_role = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(
        self,
        identifiers: typing.Sequence[int] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        """Keep track of some artwork to query later.

        Args:
            data:
                All Artwork from The Met to consider.
            parent:
                An object which, if provided, holds a reference to this instance.
                It's recommended to always provide a parent for Qt models.

        """
        super().__init__(parent)

        self._identifiers = identifiers or []
        self._cache: dict[int, model_type.Artwork] = {}

    def _get_artwork(self, index: _INDEX_TYPES) -> model_type.Artwork:
        """Get the real artwork data from `index``.

        Args:
            index: Some Qt location to query from.

        Returns:
            The found artwork.

        """
        identifier = self._identifiers[index.row()]

        if identifier in self._cache:
            node = self._cache[identifier]
        else:
            node = model_type.Artwork(identifier=identifier)
            self._cache[identifier] = node

        return node

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = _DISPLAY_ROLE,
    ) -> str | None:
        """Describe the columns of this model.

        Args:
            section: The column / row to query header data for.
            orientation: If the header is horizontal or vertical (always horizontal).
            role: The chosen representation for the header.

        Returns:
            The header text, if any.

        """
        if orientation == QtCore.Qt.Orientation.Vertical:
            return None

        if section == Column.title:
            if role == _DISPLAY_ROLE:
                return "Title"

            if role == _TOOLTIP_ROLE:
                return _TITLE_TOOLTIP

            return None

        if section == Column.datetime:
            if role == _DISPLAY_ROLE:
                return "Date"

            if role == _TOOLTIP_ROLE:
                return _DATETIME_TOOLTIP

            return None

        if section == Column.artist:
            if role == _DISPLAY_ROLE:
                return "Artist"

            if role == _TOOLTIP_ROLE:
                return _ARTIST_TOOLTIP

            return None

        return None

    def columnCount(
        self, parent: _INDEX_TYPES = QtCore.QModelIndex()
    ) -> int:  # pylint: disable=invalid-name
        """Get the number of columns to show in a view by default.

        Args:
            parent: The immediate Qt location parent to look within.

        Returns:
            Show the artwork and the artist.

        """
        return 3

    def data(  # pylint: disable=too-many-return-statements
        self,
        index: _INDEX_TYPES,
        role: int = _DISPLAY_ROLE,
    ) -> str | bytes | model_type.Artwork | met_get_type.DatetimeRange | None:
        """Get any relevant data from ``index`` and show ``role``.

        Args:
            index: Some Qt source data location (row & column) to query from.
            role: The representation of ``index`` to return.

        Returns:
            The found data, if any.

        """
        column = index.column()

        if role == self.artwork_role:
            return self._get_artwork(index)

        if role == _TOOLTIP_ROLE:
            return self._get_artwork(index).get_tooltip()

        if column == Column.title:
            if role == _DISPLAY_ROLE:
                return self._get_artwork(index).get_title() or "<No title found>"

            if role == self.data_role:
                return self._get_artwork(index).get_title()

            if role == _TOOLTIP_ROLE:
                return _TITLE_TOOLTIP

            return None

        if column == Column.datetime:
            if role == _DISPLAY_ROLE:
                artwork = self._get_artwork(index)
                start, end = artwork.get_datetime_range()

                if not start:
                    if end:
                        return _get_datetime_text(end.year())

                    return "<No Datetime>"

                if not end:
                    return _get_datetime_text(start.year())

                start_year = start.year()
                end_year = end.year()

                if start_year == end_year:
                    return _get_datetime_text(start_year)

                start_text = _get_datetime_text(start_year)
                end_text = _get_datetime_text(end_year)

                return f"{start_text} - {end_text}"

            if role == _TOOLTIP_ROLE:
                return _DATETIME_TOOLTIP

            if role == self.data_role:
                return self._get_artwork(index).get_datetime_range()

            return None

        if column == Column.artist:
            if role == _DISPLAY_ROLE:
                return self._get_artwork(index).get_artist() or "<No artist found>"

            if role == self.data_role:
                return self._get_artwork(index).get_artist()

            if role == _TOOLTIP_ROLE:
                return _ARTIST_TOOLTIP

            return None

        if column == Column.thumbnail:
            if role == _DISPLAY_ROLE:
                return self._get_artwork(index).get_thumbnail_url()

            if role == self.data_role:
                try:
                    return self._get_artwork(index).get_thumbnail_data()
                except ConnectionError:
                    _LOGGER.exception(
                        'Index "%s" defines a thumbnail but we could not read it.'
                    )

                    return None
                except Exception:
                    _LOGGER.exception(
                        'Index "%s" may have thumbnail but we could not read it.'
                    )

                    return None

            if role == _TOOLTIP_ROLE:
                return "The raw thumbnail bytes to load into an image. Be careful!"

            return None

        if column == Column.classification:
            if role == _DISPLAY_ROLE:
                return (
                    self._get_artwork(index).get_classification()
                    or "<No classification>"
                )

            if role == _TOOLTIP_ROLE:
                return "The type of artwork"

            return None

        if column == Column.medium:
            if role == _DISPLAY_ROLE:
                return self._get_artwork(index).get_medium() or "<No medium>"

            if role == _TOOLTIP_ROLE:
                return "The material or method used to create the artwork"

            return None

        return None

    def index(
        self,
        row: int,
        column: int,
        parent: _INDEX_TYPES = QtCore.QModelIndex(),
    ) -> QtCore.QModelIndex:
        """Create a Qt index for ``row`` and ``column`` underneath ``parent``.

        Args:
            row: The horizontal location of some Qt index.
            column: The vertical location of some Qt index.
            parent: The starting index, if any.

        Returns:
            A valid or invalid index.

        """
        try:
            identifier = self._identifiers[row]
        except IndexError:
            _LOGGER.warning('No identifier for "%s" row was found.', row)

            return QtCore.QModelIndex()

        if column not in self._columns:
            _LOGGER.warning('No column "%s" is not valid.', column)

            return QtCore.QModelIndex()

        return self.createIndex(row, column, identifier)

    def rowCount(
        self, _: _INDEX_TYPES = QtCore.QModelIndex()
    ) -> int:  # pylint: disable=invalid-name
        """Get the rows to show in the GUI.

        Args:
            parent: The immediate parent to get the children for.

        Returns:
            The number of rows to show.

        """
        return len(self._identifiers)

    def update_artwork_identifiers(self, identifiers: list[int]) -> None:
        """Clear and refresh this model with ``identifiers``.

        Important:
            This method reuses the existing Met Museum cache because, we assume, that an
            ID will only ever point to the same Work of Art for the lifetime of the GUI.
            (If it didn't, that would be pretty weird).

        Args:
            identifiers: Some Met Museum Artwork IDs (integers) to display.

        """
        self.beginResetModel()

        self._identifiers = identifiers

        self.endResetModel()


def _get_datetime_text(year: int) -> str:
    """Keep track of years (A.D. / B.C).

    Args:
        year: A.D. years are > 0, B.C. are < 0.

    Returns:
        The found text.

    """
    if year < 0:
        return f"{-1 * year} B.C."

    return str(year)
