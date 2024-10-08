# Copyright (c) 2008, Aldo Cortesi. All rights reserved.
# Copyright (c) 2017 Dirk Hartmann
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from __future__ import annotations

import copy
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, overload

from libqtile import configurable
from libqtile.backend.base import Window
from libqtile.command.base import CommandObject, expose_command
from libqtile.command.interface import CommandError
from libqtile.config import ScreenRect

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import Any, Self

    from libqtile.command.base import ItemT
    from libqtile.group import _Group


class Layout(CommandObject, configurable.Configurable, metaclass=ABCMeta):
    """This class defines the API that should be exposed by all layouts"""

    defaults: list[tuple[str, Any, str]] = []

    def __init__(self, **config: Any) -> None:
        # name is a little odd; we can't resolve it until the class is defined
        # (i.e., we can't figure it out to define it in Layout.defaults), so
        # we resolve it here instead.
        if "name" not in config:
            config["name"] = self.__class__.__name__.lower()

        CommandObject.__init__(self)
        configurable.Configurable.__init__(self, **config)
        self.add_defaults(Layout.defaults)

        self._group: _Group | None = None

    def layout(self, windows: Sequence[Window], screen_rect: ScreenRect) -> None:
        for i in windows:
            self.configure(i, screen_rect)

    def finalize(self) -> None:
        pass

    @property
    def group(self) -> _Group:
        """
        Returns the group this layout is attached to.

        Layouts start out unattached, and are attached when the group is configured and
        each layout is cloned for every group.
        """
        if self._group is None:
            raise RuntimeError("Layout group accessed too early")
        return self._group

    def clone(self, group: _Group) -> Self:
        """Duplicate a layout

        Make a copy of this layout. This is done to provide each group with a
        unique instance of every layout.

        Parameters
        ==========
        group:
            Group to attach new layout instance to.
        """
        c = copy.copy(self)
        c._group = group
        return c

    def _items(self, name: str) -> ItemT:
        if name == "screen" and self.group.screen is not None:
            return True, []
        elif name == "group":
            return True, []
        return None

    def _select(self, name: str, sel: str | int | None) -> CommandObject | None:
        if name == "screen":
            return self.group.screen
        elif name == "group":
            return self.group
        return None

    def show(self, screen_rect: ScreenRect) -> None:
        """Called when layout is being shown"""

    def hide(self) -> None:
        """Called when layout is being hidden"""

    def swap(self, c1: Window, c2: Window) -> None:
        """Swap the two given clients c1 and c2"""
        raise CommandError(f"layout: {self.name} does not support swapping windows")

    def focus(self, client: Window) -> None:
        """Called whenever the focus changes"""

    def blur(self) -> None:
        """Called whenever focus is gone from this layout"""

    @expose_command()
    def info(self) -> dict[str, Any]:
        """Returns a dictionary of layout information"""
        return dict(name=self.name, group=self.group.name if self.group else None)

    @abstractmethod
    def add_client(self, client: Window) -> None:
        """Called whenever a window is added to the group

        Called whether the layout is current or not. The layout should just add
        the window to its internal datastructures, without mapping or
        configuring.
        """

    @abstractmethod
    def remove(self, client: Window) -> Window | None:
        """Called whenever a window is removed from the group

        Called whether the layout is current or not. The layout should just
        de-register the window from its data structures, without unmapping the
        window.

        Returns the "next" window that should gain focus or None.
        """

    @abstractmethod
    def configure(self, client: Window, screen_rect: ScreenRect) -> None:
        """Configure the layout

        This method should:

            - Configure the dimensions and borders of a window using the
              `.place()` method.
            - Call either `.hide()` or `.unhide()` on the window.
        """

    @abstractmethod
    def focus_first(self) -> Window | None:
        """Called when the first client in Layout shall be focused.

        This method should:
            - Return the first client in Layout, if any.
            - Not focus the client itself, this is done by caller.
        """

    @abstractmethod
    def focus_last(self) -> Window | None:
        """Called when the last client in Layout shall be focused.

        This method should:
            - Return the last client in Layout, if any.
            - Not focus the client itself, this is done by caller.
        """

    @abstractmethod
    def focus_next(self, win: Window) -> Window | None:
        """Called when the next client in Layout shall be focused.

        This method should:
            - Return the next client in Layout, if any.
            - Return None if the next client would be the first client.
            - Not focus the client itself, this is done by caller.

        Do not implement a full cycle here, because the Groups cycling relies
        on returning None here if the end of Layout is hit,
        such that Floating clients are included in cycle.

        Parameters
        ==========
        win:
            The currently focused client.
        """

    @abstractmethod
    def focus_previous(self, win: Window) -> Window | None:
        """Called when the previous client in Layout shall be focused.

        This method should:
            - Return the previous client in Layout, if any.
            - Return None if the previous client would be the last client.
            - Not focus the client itself, this is done by caller.

        Do not implement a full cycle here, because the Groups cycling relies
        on returning None here if the end of Layout is hit,
        such that Floating clients are included in cycle.

        Parameters
        ==========
        win:
            The currently focused client.
        """

    @abstractmethod
    def next(self) -> None:
        pass

    @abstractmethod
    def previous(self) -> None:
        pass


class _ClientList:
    """
    ClientList maintains a list of clients and a current client.

    The collection is meant as a base or utility class for special layouts,
    which need to maintain one or several collections of windows, for example
    Columns or Stack, which use this class as base for their internal helper.

    The property 'current_index' get and set the index to the current client,
    whereas 'current_client' property can be used with clients directly.

    The collection implements focus_xxx methods as desired for Group.
    """

    def __init__(self) -> None:
        self._current_idx: int = 0
        self.clients: list[Window] = []

    @property
    def current_index(self) -> int:
        return self._current_idx

    @current_index.setter
    def current_index(self, x: int) -> None:
        if len(self):
            self._current_idx = abs(x % len(self))
        else:
            self._current_idx = 0

    @property
    def current_client(self) -> Window | None:
        if not self.clients:
            return None
        return self.clients[self._current_idx]

    @current_client.setter
    def current_client(self, client: Window) -> None:
        self._current_idx = self.clients.index(client)

    def focus(self, client: Window) -> None:
        """
        Mark the given client as the current focused client in collection.
        This is equivalent to setting current_client.
        """
        self.current_client = client

    def focus_first(self) -> Window | None:
        """
        Returns the first client in collection.
        """
        return self[0]

    def focus_next(self, win: Window) -> Window | None:
        """
        Returns the client next from win in collection.
        """
        try:
            return self[self.index(win) + 1]
        except IndexError:
            return None

    def focus_last(self) -> Window | None:
        """
        Returns the last client in collection.
        """
        return self[-1]

    def focus_previous(self, win: Window) -> Window | None:
        """
        Returns the client previous to win in collection.
        """
        idx = self.index(win)
        if idx > 0:
            return self[idx - 1]
        return None

    def add_client(
        self, client: Window, offset_to_current: int = 0, client_position: str | None = None
    ) -> None:
        """
        Insert the given client into collection at position of the current.

        Use parameter 'offset_to_current' to specify where the client shall be
        inserted. Defaults to zero, which means at position of current client.
        Positive values are after the client.

        Use parameter 'client_position' to insert the given client at 4 specific
        positions: top, bottom, after_current, before_current.
        """
        if client_position is not None:
            if client_position == "after_current":
                return self.add_client(client, offset_to_current=1)
            elif client_position == "before_current":
                return self.add_client(client, offset_to_current=0)
            elif client_position == "top":
                self.append_head(client)
            else:  # ie client_position == "bottom"
                self.append(client)
        else:
            pos = max(0, self._current_idx + offset_to_current)
            if pos < len(self.clients):
                self.clients.insert(pos, client)
            else:
                self.clients.append(client)
        self.current_client = client

    def append_head(self, client: Window) -> None:
        """
        Append the given client in front of list.
        """
        self.clients.insert(0, client)

    def append(self, client: Window) -> None:
        """
        Append the given client to the end of the collection.
        """
        self.clients.append(client)

    def remove(self, client: Window) -> Window | None:
        """
        Remove the given client from collection.
        """
        if client not in self.clients:
            return None
        idx = self.clients.index(client)
        del self.clients[idx]
        if len(self) == 0:
            self._current_idx = 0
        elif idx <= self._current_idx:
            self._current_idx = max(0, self._current_idx - 1)

        return self[self._current_idx]

    def rotate_up(self, maintain_index: bool = True) -> None:
        """
        Rotate the list. The first client is moved to last position.
        If maintain_index is True the current_index is adjusted,
        such that the same client stays current and goes up in list.
        """
        if len(self.clients) > 1:
            self.clients.append(self.clients.pop(0))
            if maintain_index:
                self.current_index -= 1

    def rotate_down(self, maintain_index: bool = True) -> None:
        """
        Rotate the list. The last client is moved to first position.
        If maintain_index is True the current_index is adjusted,
        such that the same client stays current and goes down in list.
        """
        if len(self.clients) > 1:
            self.clients.insert(0, self.clients.pop())
            if maintain_index:
                self.current_index += 1

    def swap(self, c1: Window, c2: Window, focus: int = 1) -> None:
        """
        Swap the two given clients in list.
        The optional argument 'focus' can be 1 or 2.
        In case of 1, the first client c1 is focused, in case of 2 the c2 and
        the current_index is not changed otherwise.
        """
        i1 = self.clients.index(c1)
        i2 = self.clients.index(c2)
        self.clients[i1], self.clients[i2] = self.clients[i2], self.clients[i1]
        if focus == 1:
            self.current_index = i1
        elif focus == 2:
            self.current_index = i2

    def shuffle_up(self, maintain_index: bool = True) -> None:
        """
        Shuffle the list. The current client swaps position with its predecessor.
        If maintain_index is True the current_index is adjusted,
        such that the same client stays current and goes up in list.
        """
        idx = self._current_idx
        if idx > 0:
            self.clients[idx], self.clients[idx - 1] = self.clients[idx - 1], self.clients[idx]
            if maintain_index:
                self.current_index -= 1

    def shuffle_down(self, maintain_index: bool = True) -> None:
        """
        Shuffle the list. The current client swaps position with its successor.
        If maintain_index is True the current_index is adjusted,
        such that the same client stays current and goes down in list.
        """
        idx = self._current_idx
        if idx + 1 < len(self.clients):
            self.clients[idx], self.clients[idx + 1] = self.clients[idx + 1], self.clients[idx]
            if maintain_index:
                self.current_index += 1

    def join(self, other: _ClientList, offset_to_current: int = 0) -> None:
        """
        Add clients from 'other' _ClientList to self.
        'offset_to_current' works as described for add()
        """
        pos = max(0, self.current_index + offset_to_current)
        if pos < len(self.clients):
            self.clients = self.clients[:pos:] + other.clients + self.clients[pos::]
        else:
            self.clients.extend(other.clients)

    def index(self, client: Window) -> int:
        return self.clients.index(client)

    def __len__(self) -> int:
        return len(self.clients)

    @overload
    def __getitem__(self, i: int) -> Window | None: ...

    @overload
    def __getitem__(self, i: slice) -> list[Window]: ...

    def __getitem__(self, i: int | slice) -> Window | None | list[Window]:
        if isinstance(i, slice):
            return self.clients[i]
        try:
            return self.clients[i]
        except IndexError:
            return None

    def __setitem__(self, i: int, value: Window) -> None:
        self.clients[i] = value

    def __iter__(self) -> Iterator[Window]:
        return self.clients.__iter__()

    def __contains__(self, client: Window) -> bool:
        return client in self.clients

    def __str__(self) -> str:
        curr = self.current_client
        return "_ClientList: " + ", ".join(
            [("[%s]" if c == curr else "%s") % c.name for c in self.clients]
        )

    @expose_command()
    def info(self) -> dict[str, Any]:
        return dict(
            clients=[c.name for c in self.clients],
            current=self._current_idx,
        )


class _SimpleLayoutBase(Layout):
    """
    Basic layout class for simple layouts,
    which need to maintain a single list of clients.
    This class offers full fledged list of clients and focus cycling.

    Basic Layouts like Max and Matrix are based on this class
    """

    def __init__(self, **config: Any) -> None:
        Layout.__init__(self, **config)
        self.clients = _ClientList()

    def clone(self, group: _Group) -> Self:
        c = Layout.clone(self, group)
        c.clients = _ClientList()
        return c

    def focus(self, client: Window) -> None:
        self.clients.current_client = client

    def focus_first(self) -> Window | None:
        return self.clients.focus_first()

    def focus_last(self) -> Window | None:
        return self.clients.focus_last()

    def focus_next(self, window: Window) -> Window | None:
        return self.clients.focus_next(window)

    def focus_previous(self, window: Window) -> Window | None:
        return self.clients.focus_previous(window)

    def previous(self) -> None:
        if self.clients.current_client is None:
            return
        client = self.focus_previous(self.clients.current_client) or self.focus_last()
        self.group.focus(client, True)

    def swap(self, window1: Window, window2: Window) -> None:
        self.clients.swap(window1, window2)
        self.group.layout_all()
        self.group.focus(window1)

    def next(self) -> None:
        if self.clients.current_client is None:
            return
        client = self.focus_next(self.clients.current_client) or self.focus_first()
        self.group.focus(client, True)

    def add_client(
        self, client: Window, offset_to_current: int = 0, client_position: str | None = None
    ) -> None:
        self.clients.add_client(client, offset_to_current, client_position)

    def remove(self, client: Window) -> Window | None:
        return self.clients.remove(client)

    def get_windows(self) -> list[Window]:
        return self.clients.clients

    @expose_command()
    def info(self) -> dict[str, Any]:
        d = Layout.info(self)
        d.update(self.clients.info())
        return d
