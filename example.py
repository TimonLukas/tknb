from examples.example_gui import ExampleGui

counter = 0
gui = ExampleGui("Increment example")


def increment_counter():
    global counter, gui
    counter += 1
    gui.update_label(counter)


gui.on("increment", increment_counter)
