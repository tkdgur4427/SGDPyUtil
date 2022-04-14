import debugpy
from SGDPyUtil.singleton_utils import SingletonInstance


class DebugPyContext(SingletonInstance):
    def __init__(self):
        """
        please make sure to be same as debugger port number!
        in vscode, add this json content to launch.json:
        {
            "name": "Python Debugging",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 6679 <= this should be same!
            },
            "timeout": 30000
        }
        """
        self.port_number = 6679
        # whether we call start_to_listen_debugger or not
        self.is_listening = False


def debugpy_port_number():
    return DebugPyContext.instance().port_number


def start_to_listen_debugger():
    if not DebugPyContext.instance().is_listening:
        debugpy.listen(debugpy_port_number())
        DebugPyContext.instance().is_listening = True


def wait_for_attach():
    start_to_listen_debugger()
    if not debugpy.is_client_connected():
        debugpy.wait_for_client()


def breakpoint(enable_wait_for_attach=False):
    if enable_wait_for_attach:
        wait_for_attach()
    # set debug breakpoint
    debugpy.breakpoint()
