import inspect


class FunctionObject:
    """function object"""

    def __init__(self, function, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def call(self):
        self.function(*self.args, **self.kwargs)
        return


def inspect_args(function, *args, **kwargs) -> dict:
    """generate dict for function's [(argument_name, argument_value)...]"""
    bound_args = inspect.signature(function).bind(*args, **kwargs)
    bound_args.apply_defaults()
    return bound_args.arguments
