import atexit

from tknb.gui import Gui  # noqa
from tknb.gui_proxy import GuiProxy as _GuiProxy
from tknb.util import debounce  # noqa


atexit.register(_GuiProxy.kill_all_instances)
