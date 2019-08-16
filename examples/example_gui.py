from tkinter import Label, Button

from tknb import Gui


class ExampleGui(Gui):
    def __init__(self, window_title: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.root.title(window_title)

        self.label = Label(self.root)
        self.label.grid(row=0)
        self.update_label(0)

        self.button = Button(self.root, text="Increment!", command=lambda: self.emit("increment", None))
        self.button.grid(row=1)

        self.loop()

    def update_label(self, count: int) -> None:
        self.label["text"] = f"Button has been clicked {count} times"
