import queue
import threading

from SGDPyUtil.singleton_utils import SingletonInstance
from SGDPyUtil.logging_utils import Logger


class ProcessItem:
    def __init__(self, process_name, process_instance):
        self.name = process_name
        self.instance = process_instance
        self.stdout = queue.Queue()
        return


class ProcessManager(SingletonInstance):
    def __init__(self, *args, **kargs):
        # define process container (unique_process_name, process)
        self.process_container = {}

        return

    def add_process(self, process_name, process_instance):
        if process_name in self.process_container:
            Logger.instance().info(
                f"[FAILED] try to add process with same name[{process_name}]"
            )
            return False

        # try to add new process
        self.process_container[process_name] = ProcessItem(
            process_name, process_instance
        )
        Logger.instance().info(f"[SUCCESS] succssfully add new process[{process_name}]")

        # define entry function running in stdout_thread
        def enqueue_process_stdout(process_item: ProcessItem):
            for line in iter(process_item.instance.stdout.readline, b""):
                process_item.stdout.put(f"[{process_item.name}]{line}")
            return

        # make thread to log stdout
        stdout_thread = threading.Thread(
            target=enqueue_process_stdout,
            args=(self.process_container[process_name],),
            daemon=True,
        )
        stdout_thread.start()

        return True

    def tick(self):

        # looping process
        for process_name, process_item in self.process_container.items():

            # log accumulated stdout lines
            while not process_item.stdout.empty():
                # get the line
                line = process_item.stdout.get()

                # log the stdout line
                Logger.instance().info(f"[{process_item.name}]{line}")

        return

    def terminate(self):
        return
