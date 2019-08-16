import atexit
import os
import tkinter
from abc import ABC
from multiprocessing.connection import Client, Connection
from typing import Type, Callable, Any

from tknb.constants import (
    GUI_CREATION_ENV_VARIABLE,
    SOCKET_PORT,
    SOCKET_POLL_TIMEOUT,
)
from tknb.gui_proxy import GuiProxy
from tknb.queue_message import MessageType


class Gui(ABC):
    """Base class for custom GUIs

    Extend this to implement your own GUIs. When the class is instantiated,
    the GUI will be created in a subprocess, and you will get a proxy object
    that proxies all calls to the subprocess through sockets. Be careful to
    not spam the connection, as there is some overhead.
    A `debounce` function is included for this purpose.
    """

    def __new__(cls: "Type[Gui]", *args, **kwargs):
        # A Gui cannot be instantiated directly, it must be subclassed
        if cls == Gui:
            raise AssertionError("You cannot instantiate tknb.GUI directly!")

        # If this is set, we are in the subprocess
        # This means we have to create the actual GUI instance
        if GUI_CREATION_ENV_VARIABLE in os.environ:
            return super().__new__(cls)

        # We are in the user process
        # This means we have to create
        # 1) the new thread that
        # 2) creates the subprocess
        # We return a GUI proxy that proxies all calls through the thread to
        # the subprocess
        return GuiProxy(cls, args, kwargs)

    @classmethod
    def create(cls):
        # Create the socket connection
        # Listener is static on GuiProxy class
        connection = Client(("localhost", SOCKET_PORT))

        # The connection _might_ have been closed correctly.
        # There is no easy way to check this, so we have to make do with this.
        def try_close():
            try:
                connection.send("close")
                connection.close()
            except:  # noqa
                pass

        atexit.register(try_close)

        # Initialization arguments for the class will be sent through the
        # socket connection as the first message
        args, kwargs = connection.recv()

        # Since this is just called by a script that doesn't care for the
        # return value, we don't need to return here
        cls(*args, **{**kwargs, "connection": connection})

    def __init__(self, *args, connection: Connection, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection = connection

        self.root = tkinter.Tk()

    def kill(self) -> None:
        """Kills this GUI as well as the socket connection"""
        pass

    def loop(self) -> None:
        """Run the tkinter loop, and poll for socket messages"""
        gui_has_been_closed = False

        def gui_closed():
            nonlocal gui_has_been_closed
            gui_has_been_closed = True

        # Register `gui_closed` as protocol handler for closing the window
        self.root.protocol("WM_DELETE_WINDOW", gui_closed)

        while not gui_has_been_closed:
            # Do we still have data in the connection waiting to be read?
            while self.connection.poll(SOCKET_POLL_TIMEOUT):
                message_type, command_name, arguments = self.connection.recv()
                if message_type == MessageType.METHOD_CALL:
                    method_args, method_kwargs = arguments
                    getattr(self, command_name)(*method_args, **method_kwargs)
            # Update the tkinter GUI
            self.root.update_idletasks()
            self.root.update()

        # GUI has been closed, so close all connected resources
        self.root.destroy()
        self.connection.send("close")
        self.connection.close()

    def on(self, event_name: str, handler: Callable) -> None:
        """Registers a new event handler for custom events

        :param event_name: Choose any name you want to give the event
        :param handler: An event handler
        """
        pass

    def emit(self, event_name: str, value: Any) -> None:
        """Emits a custom event to all fitting subscribed event handlers

        :param event_name: The name of your event
        :param value: what you want to pass. All picklable values are allowed.
        """
        self.connection.send((MessageType.CUSTOM_EVENT, event_name, value))
