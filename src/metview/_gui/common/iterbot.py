"""Helper functions to make iterating over Qt objects easier.

These functions are meant to be as generic as possible.

"""

import typing

from PySide6 import QtCore


T = typing.TypeVar("T")


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
