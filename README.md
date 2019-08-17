# tknb
**I uploaded this in its' current state so I could get some feedback on this project.
Things are prone to change, which is why it's not yet on PyPi. If you have feedback, please send me an e-mail or open an issue, I want to make this a good and useful thing!**

`tknb` (tkinter non-blocking) is a library that allows you to write, well, non-blocking `tkinter` GUIs.
If you've ever tried to add a GUI in Python in a separate thread, be it because you add it as an afterthought or for any other reason,
you'll know how annoying this is - there are strange, platform-specific bugs, and you basically have to architecture your project around this.

A GUI created using `tknb` will look like any other `tkinter` GUI, the implementation is completely intransparent to your code.
You get all the cool features without any additional work!

I originally wanted to name this project `nbtk` (non-blocking tkinter), but that sounds really similar to `nltk`, so I had to do the heroic thing and choose a slightly less-cool name.

## Technical implementation
When creating a GUI instance, you actually create a proxy.
This proxy will create a separate thread which spawns a subprocess. This subprocess contains your GUI.

An example for a GUI that has both "code &rarr; GUI"-communication as well as "GUI &rarr; code" can be found in `example.py`.

### Your code &rarr; GUI
If you call any methods on the GUI, the call information will be sent to the thread through a queue.
The queue is continuously polled by the thread, and any information in it is sent through a socket to the subprocess.
The subprocess polls the socket connection, and any method calls are executed on the GUI.

If you for example want to create a GUI that has a label, and you want to dynamically update the content:

**example_gui.py**
```python
from tkinter import Label
from tknb import Gui

class ExampleGui(Gui):
    def __init__(self, window_title: str, *args, **kwargs):
        # Some custom stuff has to be passed, so you must accept *args and **kwargs
        super().__init__(*args, **kwargs)
        
        # self.root is a tkinter.Tk object created by the library
        # It's the "root object" for your GUI
        self.root.title(window_title)
        
        self.label = Label(self.root, text="Hello world!")
        self.label.grid(row=0)
    
    def update_label(self, text: str) -> None:
        self.label["text"] = text
```

**main.py**
```python
import time

from example_gui import ExampleGui

gui = ExampleGui("GUI example: code to GUI communication")
time.sleep(1)
gui.update_label("Hello Github user!")
```

### GUI &rarr; your code
Calls the other way around aren't quite as easy. To accommodate the event-driven nature of GUIs, I implemented an event-subscriber-model, inspired by Node.
Your code outside of the GUI can subscribe to events (identified by strings), and your code inside the GUI can emit them.
They are again sent through the socket to the thread, and from there emitted to your own code.

**example_gui.py**
```python
from tkinter import Button
from tknb import Gui

class ExampleGui(Gui):
    def __init__(self, window_title: str, *args, **kwargs):
        # Some custom stuff has to be passed, so you must accept *args and **kwargs
        super().__init__(*args, **kwargs)
        
        # self.root is a tkinter.Tk object created by the library
        # It's the "root object" for your GUI
        self.root.title(window_title)
        
        self.click_counter = 0
        self.button = Button(self.root, text="Click me!", command=self.button_clicked)
        self.button.grid(row=0)
    
    def button_clicked(self):
        self.emit("clicked", f"Button was clicked {self.click_counter} times!")
        self.click_counter += 1
```

**main.py**
```python
from example_gui import ExampleGui

gui = ExampleGui("GUI example: GUI to code communication")
gui.on("clicked", lambda value: print(value))
```

## To Do
- [ ] Make constants configurable by user code