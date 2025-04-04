"""A widget that can easily "open" and "close", at will.

Elypson/qt-collapsible-section
(c) 2016 Michael A. Voelkel - michael.alexander.voelkel@gmail.com

This file is part of Elypson/qt-collapsible section.

Elypson/qt-collapsible-section is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, version 3 of the License, or
(at your option) any later version.

Elypson/qt-collapsible-section is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU General Public License
along with Elypson/qt-collapsible-section. If not, see <http:#www.gnu.org/licenses/>.

"""

import typing

from PySide6 import QtCore, QtWidgets


class SectionHider(QtWidgets.QWidget):
    """A widget that opens and closes, on-click.

    References:
        https://raw.githubusercontent.com/MichaelVoelkel/qt-collapsible-section/abf0cd3fb9408922f6645b61de15b2b34e7fe686/Section.py
        https://stackoverflow.com/questions/32476006/how-to-make-an-expandable-collapsable-section-widget-in-qt#
        https://stackoverflow.com/questions/52615115/how-to-create-collapsible-box-in-pyqt/52617714#52617714

    Attributes:
        toggled:
            A public signal which can be used to ask this instance to open /
            close its group.

    """

    toggled = QtCore.Signal(bool)

    def __init__(
        self,
        title: str="",
        duration: int=100,
        layout: QtWidgets.QLayout | None=None,
        parent: QtWidgets.QWidget | None=None,
    ) -> None:
        """Keep track of a top-level label, plus some optional child data.

        Args:
            title:
                A word or phrase to show the user, which explains the contents
                within this widget.
            duration:
                The time, in milliseconds, that it takes for this widget to
                open / close whenever its button is pressed. If 0, the widget
                expands / collapses instantly.
            layout:
                If included, this layout is immediately used. If not, then it's
                the user's responsibility to call
                :meth:`SectionHider.set_content_layout` so that this widget has
                some data to show / hide.
            parent:
                An object which, if provided, holds a reference to this instance.

        Raises:
            ValueError: If ``duration`` will not animate correctly.

        """
        if duration < 0:
            raise ValueError(
                'Duration "{duration}" cannot be less than zero.'.format(duration=duration)
            )

        super(SectionHider, self).__init__(parent=parent)

        main_layout = QtWidgets.QGridLayout()
        self.setLayout(main_layout)

        self._duration = duration

        self._toggle_button = QtWidgets.QToolButton()
        self._header = QtWidgets.QFrame()
        self._toggle_animation = QtCore.QParallelAnimationGroup()
        self._main_content = QtWidgets.QScrollArea()

        row = 0
        main_layout.addWidget(self._toggle_button, row, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(self._header, row, 2, 1, 1)
        main_layout.addWidget(self._main_content, row + 1, 0, 1, 3)

        self._toggle_button.setText(title)

        self._initialize_appearance_settings()
        self._initialize_default_settings()

        if not layout:
            self._initialize_default_layout()

        self._initialize_interactive_settings()

    def _initialize_appearance_settings(self) -> None:
        """Change the children of this instance to display as expected."""
        self._toggle_button.setStyleSheet("QToolButton { border: none; }")
        self._toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(False)

        self._header.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self._header.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self._header.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )

        self._main_content.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        # start out collapsed
        self._main_content.setMaximumHeight(0)
        self._main_content.setMinimumHeight(0)

        # let the entire widget grow and shrink with its content
        self._toggle_animation.addAnimation(
            QtCore.QPropertyAnimation(self, QtCore.QByteArray(b"minimumHeight"))
        )
        self._toggle_animation.addAnimation(
            QtCore.QPropertyAnimation(self, QtCore.QByteArray(b"maximumHeight"))
        )
        self._toggle_animation.addAnimation(
            QtCore.QPropertyAnimation(self._main_content, QtCore.QByteArray(b"maximumHeight"))
        )

        layout = typing.cast(QtWidgets.QGridLayout | None, self.layout())

        if not layout:
            raise RuntimeError('No SectionHider main layout.')

        layout.setVerticalSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

    def _initialize_default_layout(self) -> None:
        """Force this widget instance to use an "empty" layout.

        This method should only be called when the user has no provided a
        layout.  The reason why we need to call this at all is because this
        widget, :class:`SectionHider`, cannot be layout-less or it will cause
        Qt warnings. This method is a last-resort to prevent any issues.

        """
        layout = QtWidgets.QVBoxLayout()
        layout.addItem(
            QtWidgets.QSpacerItem(
                1,
                5,
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        )
        self.set_content_layout(layout)

    def _initialize_default_settings(self) -> None:
        """Add default settings for all children in this instance."""
        for widget, name in [
            (self._header, "_header"),
            (self._main_content, "_main_content"),
            (self._toggle_animation, "_toggle_animation"),
            (self._toggle_button, "_toggle_button"),
        ]:
            widget.setObjectName(name)

    def _initialize_interactive_settings(self) -> None:
        """Set up any click / signal behavior."""

        def _on_finished() -> None:
            self.toggled.emit(self._toggle_button.isChecked())

        self._toggle_animation.finished.connect(_on_finished)
        self._toggle_button.toggled.connect(self._toggle_start)

    def _toggle_start(self, show: bool) -> None:
        """Show or hide the content layout of this instance.

        Args:
            show:
                If ``True``, show the content layout. If ``False``, hide all
                content layout widget(s).

        Raises:
            RuntimeError:
                If this method was called before
                :meth:`SectionHider.set_content_layout` at least once.

        """
        if show:
            self._toggle_button.setArrowType(QtCore.Qt.ArrowType.DownArrow)
            self._toggle_animation.setDirection(QtCore.QAbstractAnimation.Direction.Forward)
        else:
            self._toggle_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
            self._toggle_animation.setDirection(QtCore.QAbstractAnimation.Direction.Backward)

        if not self._main_content.layout():
            raise RuntimeError("No widget content was found. Cannot expand / collapse.")

        self._toggle_animation.start()

    def set_content_layout(self, layout: QtWidgets.QWidget | QtWidgets.QLayout) -> None:
        """Set ``layout`` to be the main layout of this instance.

        Any existing layout will be replaced by ``layout``. If ``layout`` is
        actually a widget then a layout will be made for you.

        Args:
            layout:
                What we choose to display in this instance. It's assumed that
                this layout has 1+ widget which has a non-zero size.

        """
        if not isinstance(layout, QtWidgets.QLayout):
            layout_ = layout
            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(layout_)

        existing_layout = self._main_content.layout()

        if existing_layout:
            widget_to_go_out_of_scope = QtWidgets.QWidget()
            widget_to_go_out_of_scope.setLayout(existing_layout)

        self._main_content.setLayout(layout)
        collapsed_height = self.sizeHint().height() - self._main_content.maximumHeight()
        content_height = layout.sizeHint().height()

        for index in range(self._toggle_animation.animationCount() - 1):
            section_animation = self._toggle_animation.animationAt(index)

            if not isinstance(section_animation, QtCore.QPropertyAnimation):
                raise RuntimeError(
                    f'Animation "{section_animation}" is invalid. '
                    'We expected a QPropertyAnimation.',
                )

            section_animation.setDuration(self._duration)
            section_animation.setStartValue(collapsed_height)
            section_animation.setEndValue(collapsed_height + content_height)

        content_animation = self._toggle_animation.animationAt(
            self._toggle_animation.animationCount() - 1
        )

        if not isinstance(content_animation, QtCore.QPropertyAnimation):
            raise RuntimeError(
                f'Animation "{content_animation}" is invalid. '
                'We expected a QPropertyAnimation.',
            )

        content_animation.setDuration(self._duration)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)

    def set_frame_shape(self, shape: QtWidgets.QFrame.Shape) -> None:
        """Change this expandable section's appearance to ``shape``.

        This is useful for removing the section's border / frame.

        Args:
            shape: The new shape to use.

        """
        self._main_content.setFrameShape(shape)
