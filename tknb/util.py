from typing import Callable, TypeVar, Any
from time import time

T = TypeVar("T")


def _false_lambda(*args, **kwargs):
    return False


def debounce(
    duration: float,
    func: Callable[..., T],
    exception: Callable[..., bool] = None,
) -> Callable[..., T]:
    """Debounces function calls (to prevent e. g. spamming socket connections).

    :param duration: Only one message will be sent per [duration] seconds
    :param func: The function that will be debounced
    :param exception: A lambda that describes exceptions to the debouncing.
    Returns True if should not be debounced.
    :return: A callable that wraps the supplied function and debounces calls
    """
    if exception is None:
        exception = _false_lambda

    last_execution_time = 0

    def debounced(*args, **kwargs):
        nonlocal last_execution_time

        # If the lambda identifies the current parameters as an exception to
        # the debouncing progress, just pass them to the function
        if exception(*args, **kwargs):
            return func(*args, **kwargs)

        current_time = time()
        if current_time - last_execution_time > duration:
            # Update the last execution time
            last_execution_time = current_time
            return func(*args, **kwargs)

    return debounced
