"""Helper functions to make iterating over Qt objects easier.

These functions are meant to be as generic as possible.

"""

import collections
import itertools
import typing

from PySide6 import QtCore

from . import qt_constant


T = typing.TypeVar("T")


def _iter_model_indices(
    index: QtCore.QModelIndex,
    model: QtCore.QAbstractItemModel,
) -> typing.Generator[QtCore.QModelIndex, None, None]:
    """Traverse all model for indices, starting at ``index``.

    - This is a DFS (depth first search) traversal
    - Is **inclusive** (``index`` is the first yielded result).
    - Iterates rows first, then columns.

    Args:
        index: The index to start searching for child indices, if any.
        model: The source location of `index`.

    Yields:
        Each found index.

    """
    yield index

    for row, column in itertools.product(
        range(model.rowCount(index)), range(model.columnCount(index))
    ):
        child = model.index(row, column, parent=index)

        for grand_child in _iter_model_indices(child, model):
            yield grand_child


def get_all_models_by_type(
    model: QtCore.QAbstractItemModel,
    type_: typing.Type[T],
) -> list[T]:
    """Find every Qt proxy / model starting from ``model`` of ``type_`` class type.

    Important:
        This method is **inclusive**, meaning ``model`` may be included in the return.

    Args:
        model: Some Qt proxy or source to begin searching within.
        type_: The Qt class to look within.

    Returns:
        All found matches, if any.

    """
    output: list[T] = []

    while hasattr(model, "sourceModel"):
        if isinstance(model, type_):
            output.append(model)

        model = model.sourceModel()

    if model and isinstance(model, type_):
        output.append(model)

    return output


def get_lowest_source(model: QtCore.QAbstractItemModel) -> QtCore.QAbstractItemModel:
    """Find the lower-most source model, starting from ``model``.

    Args:
        model: The proxy to search within.

    Returns:
        The found source model.

    """
    while hasattr(model, "sourceModel"):
        model = model.sourceModel()

    return model


def get_sibling_range(
    index: QtCore.QModelIndex,
    direction: str="all",
) -> tuple[QtCore.QModelIndex, QtCore.QModelIndex]:
    """Get the column siblings of ``index``.

    Note:
        This function is **inclusive**. It will always include ``index`` in its output.

    Note:
        For some model...

        - root index
            - row N column 0, row N column 1, row N column 2, row N column 3

        direction = "all" with ``row N column 1`` would return:

        [``row N column 0``, ``row N column 3``]

        direction = "left" with ``row N column 1`` would return:

        [``row N column 0``, ``row N column 1``]

        direction = "right" with ``row N column 1`` would return:

        [``row N column 1``, ``row N column 2``, ``row N column 3``]

    Args:
        index:
            The point from which to return other sibling indices.
        direction:
            A description of the siblings to return. See notes for details.

    Raises
        ValueError: If ``direction`` is unknown.

    Returns:
        The start and end range for each sibling.

    """
    parent = index.parent()
    model = index.model()
    row = index.row()

    first_column = 0

    if direction == "all":
        minimum = model.index(row, first_column, parent=parent)
        maximum = model.index(row, model.columnCount(parent) - 1, parent=parent)
    elif direction == "left":
        minimum = model.index(row, first_column, parent=parent)
        maximum = index
    elif direction == "right":
        minimum = index
        maximum = model.index(row, model.columnCount(parent) - 1, parent=parent)
    else:
        raise ValueError(
            'Direction "{direction}" is invalid. Options were "{options}".'.format(
                direction=direction,
                options=", ".join(("all", "left", "right")),
            )
        )

    return minimum, maximum


def iter_child_indices(
    index: QtCore.QModelIndex,
    model: QtCore.QAbstractItemModel | None = None,
) -> typing.Generator[QtCore.QModelIndex, None, None]:
    """Traverse all indices on-and-under ``index``.

    - This is a DFS (depth first search) traversal
    - Is **inclusive** (root-level indices are included & yielded).
    - Iterates rows first, then columns.

    Args:
        index: A index to check for chiindices.
        model: The source location of ``index``.

    Yields:
        Each found index.

    """
    model = model or index.model()

    for child in _iter_model_indices(index, model):
        yield child


def iter_model_row_indices(
    model: QtCore.QAbstractItemModel,
) -> typing.Generator[QtCore.QModelIndex, None, None]:
    """Get every index in ``model`` recursively but only one index per-row.

    Args:
        model: Some Qt data to inspect.

    Yields:
        The found indices.

    """
    parent = QtCore.QModelIndex()
    stack = [
        model.index(row, qt_constant.CHILD_COLUMN, parent)
        for row in range(model.rowCount(parent))
    ]
    seen = set()

    while stack:
        current = stack.pop()

        if current in seen:
            continue

        seen.add(current)

        for child in reversed(
            [
                model.index(row, qt_constant.CHILD_COLUMN, current)
                for row in range(model.rowCount(current))
            ]
        ):
            stack.append(child)

        yield current


def iter_unique_rows(
    indices: typing.Iterable[QtCore.QModelIndex],
    predicate: typing.Optional[typing.Callable[[QtCore.QModelIndex], bool]] = None,
) -> list[QtCore.QModelIndex]:
    """Filter ``indices`` down to only each unique row.

    Important:
        This function does not preserve the order of ``indices``.

    Args:
        indices:
            The data to uniquify.
        predicate:
            A function that, if included, is called whenever more than one index with
            the same parent / row is found. By default if no predicate is found, this
            function prefers the 0th column for a particular parent + row index. But you
            can provide your own function to do custom things if you want. 99% of the
            time, leave this parameter untouched.

    Returns:
        The uniquified indices.

    """

    def _prefer_column_0(index: QtCore.QModelIndex) -> bool:
        """Iterate over just the child columns.

        In Qt, tree information is stored on the 0th column, which we target here.

        Args:
            index: The data to query from.

        Returns:
            If ``index`` is a location that may contain children, return ``True``.

        """
        return index.column() == 0

    if not predicate:
        predicate = _prefer_column_0

    rows = collections.OrderedDict()

    for index in indices:
        key = (index.parent(), index.row())

        if key not in rows or predicate(index):
            rows[key] = index

    return list(rows.values())


def map_to_source_recursively(
    index: QtCore.QModelIndex,
    source_model: QtCore.QAbstractItemModel,
) -> QtCore.QModelIndex:
    """Convert ``index`` from whatever model it is to an index in ``source_model``.

    Args:
        index:
            The row / column / parent index to convert into a source index.
        source_model:
            The model to map into.

    Raises:
        RuntimeError: If no source index / model could be found.

    Returns:
        The found source index, using ``index``.

    """
    model = index.model()
    original = model

    current_index = index

    while (
        model != source_model
        and hasattr(model, "sourceModel")
        and hasattr(model, "mapToSource")
    ):
        current_index = model.mapToSource(current_index)

        model = model.sourceModel()

    if model != source_model:
        raise RuntimeError(
            'Model "{original}" could not be mapped to our source model, "{source_model}".'.format(
                original=original, source_model=source_model
            )
        )

    return current_index
