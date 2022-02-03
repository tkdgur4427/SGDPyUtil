""" event queue """
from queue import Queue
from threading import Event

# logging
from SGDPyUtil.logging_utils import Logger

# function
from SGDPyUtil.function_utils import FunctionObject


class EventCommand:
    """event command"""

    def __init__(
        self, execute_function: FunctionObject, callback_function: FunctionObject = None
    ):
        # capture function and its arguments
        self.task_execute = execute_function
        self.task_callback = callback_function
        return

    def execute(self):
        self.task_execute.call()
        return

    def callback(self):
        if self.task_callback != None:
            self.task_callback.call()
        return


class EventTask:
    def __init__(self, event_tag=""):
        # event tag using EventTaskQueue
        self.event_tag = event_tag
        # commands (batched command)
        self.commands: list["EventCommand"] = []
        return

    def is_sync_task(self) -> bool:
        return self.event_tag != ""

    def add_command(self, command: EventCommand):
        self.commands.append(command)
        return

    def execute(self):
        for command in self.commands:
            command.execute()
        return

    def callback(self):
        for command in self.commands:
            command.callback()
        return


class SyncErrorException(Exception):
    pass


class SyncEvent:
    def __init__(self):
        # create sync event
        self._event = Event()

        # tag information to check matching between wait() and signal()
        self.tag = ""
        # signals
        self.signal_tags: Queue[str] = Queue()

        return

    def wait(self, tag="", time_out=None):
        # mark tag
        self.tag = tag

        # wait for signal
        result = self._event.wait(time_out)

        # validate
        if result:
            self.validate()
            # reset the event
            self._event.clear()

        return result

    def validate(self):
        signal_tag = self.signal_tags.get()
        if not self.signal_tags.empty():
            Logger.instance().info(f"[SyncEvent] multiple signal called [{signal_tag}]")

            count = 0
            while not self.signal_tags.empty():
                error_signal_tag = self.signal_tags.get()
                Logger.instance().info(f"[SyncEvent]---[{count}] {error_signal_tag}")
                count = count + 1

            raise SyncErrorException

        if self.tag != signal_tag:
            Logger.instance().info(
                f"[SyncEvent] tag is mismatch [{self.tag}] and [{signal_tag}]"
            )
            raise SyncErrorException

        return

    def signal(self, tag=""):
        # add tag
        self.signal_tags.put(tag)
        # signal event
        self._event.set()


class SyncEventTaskQueue:
    def __init__(self):
        # create sync event
        self.sync_barrier = SyncEvent()

        # event tasks
        self.tasks: Queue["EventTask"] = Queue()

        # current running task
        self.curr_task: EventTask = None

        return

    def is_empty(self):
        return self.tasks.empty()

    def is_pending(self):
        return self.curr_task != None

    def signal_sync_barrier(self, tag):
        self.sync_barrier.signal(tag)
        return

    def add_task(self, task: EventTask):
        self.tasks.put(task)
        return

    def try_dispatch_once(self) -> bool:
        # until all accumulated tasks finished, looping
        if self.curr_task == None:
            # early-out when tasks is empty
            if self.is_empty():
                return False

            # get new current task
            self.curr_task = self.tasks.get()

            # execute task
            self.curr_task.execute()

        # if task is sync-task, waiting
        if not self.curr_task.is_sync_task():
            # no pending call, so call callback directly
            self.curr_task.callback()

            # mark task is finished
            self.curr_task = None
        else:
            # get the event tag
            event_tag = self.curr_task.event_tag

            # waiting until signal is triggered
            wait_time = 1.0 / 120  # 120Hz
            finished = self.sync_barrier.wait(event_tag, wait_time)

            if finished:
                # execute callback
                self.curr_task.callback()

                # finished to execute task
                self.curr_task = None

        return (not self.is_empty()) and (not self.is_pending())
