from datetime import datetime
import random
from typing import Any, Callable, Dict

from snake3.misc import Uninstantiateable


class Cancelled(Exception):
    """Gets raised as a signal that an event was cancelled midway through handler chain execution."""

    pass


class NotCancellableError(Exception):
    """Gets raised whenever an uncancellable event is attempted to be cancelled."""

    pass


class DisconnectedError(Exception):
    """Gets raised whenever an operation is attempted to be performed on a disconnected EventConnection()."""

    pass


class EventConnectFlags(Uninstantiateable):
    """Represents various flags that alter how an event connection behaves.

    Not an Enum subclass!
    """

    ONESHOT: int = 0b1
    """Event connection will be automatically disconnected after one event."""


class EventConnection:
    """Represents a connection between an event handler function and an Event().

    Attributes:
        event: The event this EventConnection() is related to (None if disconnected)
        id: A unique connection ID, used internally
        func: The handler function this EventConnection() is related to
        flags: One or more EventConnectFlags values OR'd together
    """

    def __init__(
        self, event: Event, id: int, func: Callable[[Event, Any], None], flags: int
    ) -> None:
        """Creates a new EventConnection() connected to the specified Event() and handler.

        This is NOT how you properly connect a handler to an Event(), use Event().connect() instead.
        This constructor function is meant to be used internally.

        Args:
            event: The event this EventConnection() will be related to
            id: A unique connection ID, used internally
            func: The handler function this EventConnection() will be related to.
            flags: One or more EventConnectFlags values OR'd together
        """

        self.event: Event | None = event
        self.id: int = id
        self.func: Callable[[Event, Any], None] = func
        self.flags: int = flags

    def disconnect(self) -> None:
        """Disconnects the event handler from the Event(), invalidating the EventConnection().

        Raises:
            DisconnectedError - Event connection already disconnected
        """

        if self.event:
            del self.event._connections[self.id]
            self.event = None
        else:
            raise DisconnectedError("EventConnection() has already been disconnected")


class Event:
    """Represents a fireable, cancellable and handleable event.

    An Event() is basically a container object that stores information about its handlers
    and provides a couple of methods for easily managing and interacting with them.

    An Event() can be fired via the fire() method. This triggers the attached event handlers, from
    most recently connected to least recently connected.

    A handler is a function that takes in the fired Event() as the 1st argument and an event-defined piece
    of data as the 2nd argument, returning None (equal to Callable[[Event, Any], None]). Handlers are connected
    via the Event().connect() method, which provides extra parameters (i.e. oneshot) for automating certain
    scenarios. connect() returns an EventConnection() object, which stores information about the event handler
    connection and can be used to disconnect it via EventConnection().disconnect().

    Certain Event()s can also be cancelled midway through event handler chain execution by calling
    Event().cancel() This stops the event from propogating, meaning the next handlers in the chain are
    never called. This also raises an EventCancelled exception, which can be used to trigger code that
    reverts an action if the event is cancelled. Attempting to cancel an uncancellable event will raise
    a NotCancellableError instead (which you're NOT supposed to catch).

    Attributes:
        name: The name of the event, kinda like its type.
        can_cancel: Whether the event can be cancelled or not.
    """

    def __init__(self, name: str, *, can_cancel: bool = False) -> None:
        """Creates a new blank Event() with the provided name and parameters.

        Args:
            name: The name of the event

        Kwargs:
            can_cancel: Whether the event can be cancelled or not. False by default.
        """

        self.name: str = name
        self.can_cancel: bool = False

        self._connections: Dict[int, EventConnection] = {}

    def connect(
        self, func: Callable[[Event, Any], None], flags: int
    ) -> EventConnection:
        """Connects a handler function to this Event().

        An Event() may have multiple handler functions connected to itself, however, the most
        recently connected functions will be the ones that get called first.

        Args:
            func: The event handler function to connect to the Event()
            flags: One or more EventConnectFlags values OR'd together

        Returns:
            An EventConnection() representing the connection between the Event() and the handler
        """

        evcon_id: int = int(datetime.now().timestamp())
        evcon: EventConnection = EventConnection(self, evcon_id, func, flags)
        self._connections[evcon_id] = evcon
        return evcon

    def fire(self, arg: Any) -> None:
        """Fires the Event() with the provided argument.

        This executes all connected handlers, from most recently connected to least recently connected.

        Args:
            arg: The argument to fire the event with

        Raises:
            Cancelled - The event was canceled via Event().cancel()
            (other Exception()s) - Something went wrong while handling the event
        """

        for evcon_id in reversed(self._connections.keys()):
            self._connections[evcon_id].func(self, arg)

            if self._connections[evcon_id].flags & EventConnectFlags.ONESHOT:
                self._connections[evcon_id].disconnect()

    def cancel(self) -> None:
        """Cancels this Event().

        This function should only be called from an event handler connected to this event.

        This is basically a fancier, safer to raise a Cancelled exception.

        Raises:
            Cancelled - As part of how this function works, to cancel an event
            NotCancellableError - Event isn't set as cancellable
        """

        if self.can_cancel:
            raise Cancelled("Event was cancelled")
        else:
            raise NotCancellableError("Event cannot be cancelled")
