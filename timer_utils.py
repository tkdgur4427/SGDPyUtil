import time
from enum import Enum

from SGDPyUtil.logging_utils import Logger
from SGDPyUtil.function_utils import FunctionObject


class TimerItem:
    def __init__(self, name: str, repeat_time: float, function: FunctionObject):
        self.name: str = name
        self.repeat_time = repeat_time
        self.function: FunctionObject = function

        # elapsed time
        self.remain_time: float = self.repeat_time
        return

    def reset(self):
        self.remain_time = self.repeat_time
        return

    def tick(self, duration: float):
        # if it is ready to execute function
        if self.remain_time < 0.0:
            # execute timer function
            self.function.call()

            # reset remain_time
            self.reset()

        # update remain_time
        self.remain_time = self.remain_time - duration

        return


class SequenceItem:
    def __init__(self, name, function: FunctionObject, once=False):
        self.name = name
        self.function = function

        # whether we call this sequence item once and remove item from sequence timer
        self.once = once
        return

    def call(self):
        self.function.call()
        return


class PendingSeqenceItemType(Enum):
    ADD = 0
    REMOVE = 1


class PendingSequenceItem:
    def __init__(self, type: PendingSeqenceItemType, item_or_name):
        self.item_or_name = item_or_name
        self.type = type


class TimerSequenceItem(TimerItem):
    """timer which has multiple functions to execute them in rotation"""

    def __init__(self, name: str, repeat_time: float):
        # init TimerItem class member variables
        super().__init__(name, repeat_time, None)

        # sequence number
        self.sequence = 0

        # list of items
        self.item_names = []  # this is for rotating to execute sequence item by index
        self.items = {}
        # pending sequence items
        self.pending_items = []

        return

    def add_sequence_item(self, item: SequenceItem):
        pending_item = PendingSequenceItem(PendingSeqenceItemType.ADD, item)
        self.pending_items.append(pending_item)
        return

    def remove_sequence_item(self, name):
        pending_item = PendingSequenceItem(PendingSeqenceItemType.REMOVE, name)
        self.pending_items.append(pending_item)
        return

    def tick(self, duration: float):
        # process pending items
        for item in self.pending_items:
            if item.type == PendingSeqenceItemType.ADD:
                """ADD PENDING SEQUENCE ITEM"""
                sequence_item: SequenceItem = item.item_or_name
                if sequence_item.name in self.items:
                    Logger.instance().info(
                        f"[ERROR] overlapped sequence item [{item.name}]"
                    )
                    continue
                self.items[sequence_item.name] = sequence_item
                self.item_names.append(sequence_item.name)

            elif item.type == PendingSeqenceItemType.REMOVE:
                """REMOVE PENDING SEQUENCE ITEM"""
                name: str = item.item_or_name
                if not (name in self.items):
                    Logger.instance().info(f"[ERROR] no sequence item exists [{name}]")
                    continue
                self.items.pop(name)
                self.item_names.pop(self.item_names.index(name))

        # empty pending items
        self.pending_items.clear()

        # if it is ready to execute function
        if self.remain_time < 0.0:
            # only execute if there are any function to execute
            if len(self.item_names) > 0:
                # find slot index by sequence
                index_to_execute = self.sequence % len(self.item_names)

                # find function to execute
                name = self.item_names[index_to_execute]

                # sequence item to execute
                sequence_item = self.items[name]
                sequence_item.function.call()

                # if sequence item is removed after execution, remove item
                if sequence_item.once:
                    self.remove_sequence_item(name)

                # increase sequence number
                self.sequence += 1

            # reset remain_time
            self.reset()

        # update remain_time
        self.remain_time = self.remain_time - duration

        return


class PendingTimerType(Enum):
    ADD = 0
    REMOVE = 1


class PendingTimerItem:
    def __init__(self, type: PendingTimerType, timer_or_name, callback: FunctionObject):
        self.timer_or_name = timer_or_name
        self.type = type
        self.callback_func = callback

    def callback(self):
        if self.callback_func != None:
            self.callback_func.call()


class TimerContext:
    def __init__(self):
        self.timers: dict[str, TimerItem] = {}
        self.tick_time = time.time()

        # pending list
        self.pending_timers: list[PendingTimerItem] = []

        return

    def register_timer(self, item: TimerItem, callback: FunctionObject = None):
        self.pending_timers.append(
            PendingTimerItem(PendingTimerType.ADD, item, callback)
        )
        return

    def unregister_timer(self, name, callback: FunctionObject = None):
        self.pending_timers.append(
            PendingTimerItem(PendingTimerType.REMOVE, name, callback)
        )
        return

    def get_timer(self, name):
        if not name in self.timers:
            return None

        return self.timers[name]

    def tick(self):
        # process pending timers
        for item in self.pending_timers:
            if item.type == PendingTimerType.ADD:
                """ADD PENDING TIMER"""
                timer: TimerItem = item.timer_or_name
                if timer.name in self.timers:
                    Logger.instance().info(f"[ERROR] overlapped timer [{timer.time}]")
                    continue
                self.timers[timer.name] = timer

                # call callback
                item.callback()

            elif item.type == PendingTimerType.REMOVE:
                """REMOVE PENDING TIMER"""
                name: str = item.timer_or_name
                if not (name in self.timers):
                    Logger.instance().info(f"[ERROR] no timer exists [{name}]")
                    continue
                self.timers.pop(name)

                # call callback
                item.callback()

        # clear pending_timers
        self.pending_timers.clear()

        # calculate duration
        duration = time.time() - self.tick_time

        # tick timer
        for _, timer_item in self.timers.items():
            timer_item.tick(duration)

        # update tick_time
        self.tick_time = time.time()

        return
