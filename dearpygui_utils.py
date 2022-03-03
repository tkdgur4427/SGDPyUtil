import os
from typing import Dict
from enum import Enum
import dearpygui.dearpygui as dpg

from SGDPyUtil.singleton_utils import SingletonInstance
from SGDPyUtil.logging_utils import Logger
from SGDPyUtil.function_utils import FunctionObject
from SGDPyUtil.event_utils import EventTask, SyncEventTaskQueue
from SGDPyUtil.timer_utils import *


class DearPyGuiDelegate:
    def __init__(self, name: str, execute: FunctionObject):
        self.name: str = name
        self.execute_function: FunctionObject = execute

    def execute(self):
        self.execute_function.call()


class DearPyGuiContext(SingletonInstance):
    def __init__(self):
        # app name
        self.app_name = "SGDPyUtil"

        # used for create primary window
        self.primary_window_setup: DearPyGuiDelegate = None
        return


class DearPyGuiApp(SingletonInstance):
    def __init__(self):
        """attributes"""
        self.app_name = DearPyGuiContext.instance().app_name
        self.primary_window_tag = None

        # task queue
        self.task_queue: SyncEventTaskQueue = SyncEventTaskQueue()

        # timer manager
        self.timer_manager: TimerContext = TimerContext()

        # init dearpygui
        self.width = 700
        self.height = 500

        dpg.create_context()
        dpg.create_viewport(
            title=self.app_name, width=self.width, height=self.height, resizable=True
        )
        dpg.setup_dearpygui()

        return

    def init_app(self) -> bool:
        # create primary window
        if DearPyGuiContext.instance().primary_window_setup != None:
            primary_window_setup = DearPyGuiContext.instance().primary_window_setup
            primary_window_setup.execute()

        if self.primary_window_tag == None:
            Logger.instance().info(f"[ERROR] you didn't create primary window!")
            return False

        # setup primary window for self.primary_window_tag
        dpg.set_primary_window(self.primary_window_tag, True)

        # make viewport visible
        dpg.show_viewport()

        return True

    def is_running(self) -> bool:
        return dpg.is_dearpygui_running()

    def tick(self) -> bool:
        """timer manager"""
        self.timer_manager.tick()

        """event task queue"""
        # dispatch tasks
        can_continue = True
        while can_continue:
            can_continue = self.task_queue.try_dispatch_once()

        # any remaining task?
        is_all_tasks_processed = (
            self.task_queue.is_empty() and not self.task_queue.is_pending()
        )

        """dearpygui"""
        # render dearpygui_frame
        dpg.render_dearpygui_frame()

        return is_all_tasks_processed

    def add_task(self, task: EventTask):
        self.task_queue.add_task(task)

    def signal_tag(self, tag=""):
        self.task_queue.signal_sync_barrier(tag)

    def destroy_app(self):
        dpg.destroy_context()
