import inspect
import os
import subprocess
import threading
from multiprocessing.connection import Listener
from typing import Type, List, TYPE_CHECKING, Callable, Dict, Any

from tknb.constants import (
    SOCKET_PORT,
    GUI_CREATION_ENV_VARIABLE,
    SOCKET_POLL_TIMEOUT,
)
from tknb.generic_queue import GenericQueue
from tknb.queue_message import QueueMessage, MessageType

if TYPE_CHECKING:
    from tknb.gui import Gui

_listener = None
if GUI_CREATION_ENV_VARIABLE not in os.environ:
    _listener = Listener(("localhost", SOCKET_PORT))


def _create_empty_handler_handler(handler: Callable[[], Any]) -> Callable[[Any], Any]:
    def new_handler(_: Any) -> Any:
        return handler()

    return new_handler


class GuiProxy:
    """Class that proxies all calls in a client thread to the socket GUI

    When a user creates a new subclass object of `Gui`, they will instead get
    an instance of `GuiProxy`. This instance will then create a separate
    thread which creates the subprocess containing the real GUI. All calls to
    methods on the GUI will be forwarded from this instance to the subprocess
    through sockets.
    """

    # Keep a list of all instances that are currently alive, so we can kill
    # them as necessary
    _instances: "List[GuiProxy]" = []

    @staticmethod
    def kill_all_instances():
        for instance in GuiProxy._instances:
            instance.kill()

    def __init__(self, proxied_gui_class: "Type[Gui]", args, kwargs):
        GuiProxy._instances.append(self)

        self.gui_type = proxied_gui_class

        # We need a queue to communicate with the new thread we will create
        self.queue: GenericQueue[QueueMessage] = GenericQueue()

        # Threads cannot be killed directly, so we have to keep track through
        # a custom mechanism
        self.is_alive = True

        # Create a dict that will store registered event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}

        # Save all methods the GUI instance should have
        # If a user calls a method on the proxy, we want to make sure that it
        # actually exists before sending the request
        instance_methods = inspect.getmembers(
            proxied_gui_class,
            predicate=lambda member: inspect.isfunction(member)
            and not inspect.ismethod(member),
        )
        self.gui_methods = [
            method[0]
            for method in instance_methods
            if not method[0].startswith(
                "_"
            )  # Don't want to expose protected methods
        ]

        def create(
            queue: GenericQueue[QueueMessage],
            emit: Callable[[str, Any], None],
            should_stop: Callable[[], bool],
            thread_finished: Callable[[], None],
        ):
            # Create the subprocess, and create an instance of the GUI in that
            module = proxied_gui_class.__module__
            class_name = proxied_gui_class.__name__
            process = subprocess.Popen(
                [
                    "python",
                    "-c",
                    "\n".join(
                        [
                            f"from {module} import {class_name}",
                            f"{class_name}.create()",
                        ]
                    ),
                ],
                env={**os.environ, GUI_CREATION_ENV_VARIABLE: "true"},
                stdout=None,
                stderr=None,
            )

            # The next incoming connection will be the one of the GUI created
            # in the subprocess above
            connection = _listener.accept()

            # Send the initialization parameters so the GUI can be properly
            # initialized
            connection.send((args, kwargs))

            # We can't poll `is_alive` directly (since this is a different
            # thread), so we have to use a lambda instead
            while not should_stop():
                # Is there any data available in the connection?
                # We only want to process one message at a time to keep
                # update times on the GUI short
                if connection.poll(SOCKET_POLL_TIMEOUT):
                    msg = connection.recv()

                    # If we receive a "close" message, die
                    if msg == "close":
                        connection.close()
                        break

                    # Otherwise the message is for an event created by the GUI
                    message_type, command_name, arguments = msg
                    if message_type == MessageType.CUSTOM_EVENT:
                        emit(command_name, arguments)

                # Send all messages currently in the queue through the socket
                while not queue.empty():
                    connection.send(queue.get())

            # `should_stop()` is true, so kill the process
            process.kill()
            # The thread is finished. Notify the parent of this
            thread_finished()

        thread = threading.Thread(
            target=create,
            kwargs={
                # Pass the queue instance for inter-thread-communication
                "queue": self.queue,
                # Pass the `emit` function so events can be published to the
                # respective handlers
                "emit": self.emit,
                # The thread should stop once `is_alive` is False
                "should_stop": lambda: not self.is_alive,
                # If the thread is finished, kill the proxy
                "thread_finished": self.kill,
            },
        )
        thread.start()

    # When the user tries to access any of his custom GUI methods,
    # they won't be accessible
    # This magic function catches those calls
    def __getattr__(self, item):
        """Main proxy functionality

        When the user tries to access any of his custom GUI methods,
        they won't be accessible.
        We return a lambda that, for the user, looks like his function,
        except that it puts his data into the queue, from which it will be
        pulled and sent through the socket connection,
        to the real GUI instance.
        """

        # First off check whether the method called is actually available on
        # the real GUI subclass instance
        # If not, raise the corresponding error
        if item not in self.gui_methods:
            # Not using the wording of the real error message is by design
            # We don't want the user to be confused when he looks
            # into the code and thinks "I didn't call this!"
            raise AttributeError(
                f"GUI type `{self.gui_type.__name__}` has no method `{item}`"
            )

        # Only put items into the queue if the connection is still alive
        if self.is_alive:
            return lambda *args, **kwargs: self.queue.put(
                (MessageType.METHOD_CALL, item, (args, kwargs))
            )

        # If it isn't, just throw it away
        return lambda *args, **kwargs: None

    def kill(self) -> None:
        GuiProxy._instances.remove(
            self
        )  # Now that the instance is dead, remove it from the list
        self.is_alive = False
        self.emit(
            "exit", None
        )  # Emit an "exit" event to all interested event handlers

    def on(self, event_name: str, handler: Callable) -> None:
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []

        parameter_count = len(inspect.signature(handler).parameters)
        if parameter_count > 1:
            raise AssertionError(" ".join([
                f"Handler \"{handler.__name__}\" for event \"{event_name}\" must have 0 or 1 parameters",
                f"({parameter_count} given)"
            ]))

        # Allow the user to use a handler with no parameters
        if parameter_count == 0:
            handler = _create_empty_handler_handler(handler)

        self._event_handlers[event_name].append(handler)

    def emit(self, event_name: str, value: Any) -> None:
        if event_name in self._event_handlers:
            for handler in self._event_handlers[event_name]:
                handler(value)
