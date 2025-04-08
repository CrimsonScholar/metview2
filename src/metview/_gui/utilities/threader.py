"""Basic classes to make Qt + multi-threading easier."""

import logging
import typing

from PySide6 import QtCore

from ..models import art_model, model_type

_LOGGER = logging.getLogger(__name__)


class ArtSearchWorker(QtCore.QObject):
    """Handle any high latency / slow functions here.

    Attributes:
        errored:
            If this instance finished but errored, this signal is emitted.
        finished:
            If this instance finished successfully, this signal is emitted.
        request_stop:
            A signal used externally (from the main thread) to tell this
            instance not to emit any signals and stop working ASAP.
        identifiers_found:
            After we query the Met Museum for all Artworks, the found IDs are emitted.

    """

    identifiers_found = QtCore.Signal(list)
    request_stop = QtCore.Signal()

    errored = QtCore.Signal()
    finished = QtCore.Signal()

    def __init__(
        self,
        query: typing.Callable[[], typing.Iterable[int]],
        parent: QtCore.QObject | None = None,
    ) -> None:
        """Keep track of a function that we'll use to search for identifiers, later.

        Args:
            query: Some Met REST API-like function to call.
            parent: An object which, if provided, holds a reference to this instance.

        """
        super().__init__(parent)

        self._is_running = False
        self._query = query
        self.request_stop.connect(self.stop)

    def run(self) -> None:
        """Look for Met Museum IDs and update the parent thread when it is ready."""
        try:
            self._is_running = True

            identifiers = self._query()

            # NOTE: In between this code running, the user may stop the worker, mid-run
            if self._is_running:
                self.identifiers_found.emit(identifiers)
        except Exception:
            self.errored.emit()
        finally:
            self.finished.emit()

    def stop(self) -> None:
        """Prevent this instane from emitting any "finished" signals."""
        self._is_running = False
