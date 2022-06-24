from lib2to3.pytree import Base
import os
import subprocess
import shutil

from enum import Enum
from string import Template
from typing import Dict

from SGDPyUtil.logging_utils import Logger
from SGDPyUtil.singleton_utils import SingletonInstance
from SGDPyUtil.json_utils import *
from SGDPyUtil.main import GlobalContext
from SGDPyUtil.event_utils import *
from SGDPyUtil.dearpygui_utils import *
from SGDPyUtil.powershell_utils import execute_powershell_content


class UnrealEnvContext(SingletonInstance):
    def __init__(self):
        # unreal engine source directory
        self.unreal_path = None
        # unreal project directory
        self.unreal_project_path = None
        # GenerateProjectFiles.bat path for unreal_path
        self.generate_project_file_path = None
        # current working plugin path
        self.curr_working_plugin_path = None

        # try to load unreal_setting.json
        self.setting_path = os.path.join(
            GlobalContext.instance().root_dir, "unreal_setting.json"
        )
        if os.path.exists(self.setting_path):
            # read unreal_setting.json
            json_data = read_json_data(self.setting_path)

            # parsing the data
            self.unreal_path = json_data.get("unreal_path", None)
            self.unreal_project_path = json_data.get("unreal_project_path", None)
            self.generate_project_file_path = json_data.get(
                "generate_project_file_path", None
            )
            self.curr_working_plugin_path = json_data.get(
                "curr_working_plugin_path", None
            )

            # update settings
            self.update_settings()

        return

    def update_settings(self):
        json_data = {}

        # generate json data
        if self.unreal_path != None:
            json_data["unreal_path"] = self.unreal_path
        if self.unreal_path != None:
            json_data["unreal_project_path"] = self.unreal_project_path
        if self.generate_project_file_path != None:
            json_data["generate_project_file_path"] = self.generate_project_file_path
        if self.curr_working_plugin_path != None:
            json_data["curr_working_plugin_path"] = self.curr_working_plugin_path

        write_json_data(json_data, self.setting_path)

        # check whether we have symlink of SGDUnreal to unreal source path
        # @todo - need to refactor static plugin name
        src_plugin_path = os.path.abspath(".")
        dst_plugin_path = os.path.join(self.curr_working_plugin_path, "SGDUnreal")
        if not os.path.isdir(dst_plugin_path):
            subprocess.check_call(
                f'mklink /J "{dst_plugin_path}" "{src_plugin_path}"', shell=True
            )

        Logger.instance().info(f"[UnrealEnvContext] update unreal environment settings")

        return

    def setup(self, unreal_path: str):
        self.unreal_path = unreal_path

        # derive curr_working_plugin_path
        self.curr_working_plugin_path = os.path.normpath(
            os.path.join(self.unreal_path, "Engine", "Plugins")
        )
        return


class UnrealClassType(Enum):
    RAW = 0
    UOBJECT = 1
    ACTOR = 2


class UnrealProgrammerAssistantContext(SingletonInstance):
    def __init__(self):
        # Plugin
        self.plugin_name = None
        self.plugin_path = None

        # Module
        self.module_name = None
        self.module_path = None

        # Class
        self.class_name = None
        self.class_path = None
        self.class_type: UnrealClassType = UnrealClassType.RAW


class SourceGenerator:
    def __init__(self, name: str, directory: str):
        self.name = name
        self.directory = os.path.normpath(os.path.join(directory, self.name))

    def execute_generated_project_files(self):
        file_path = UnrealEnvContext.instance().generate_project_file_path
        if not os.path.exists(file_path):
            Logger.instance().info(
                f"[ERROR] GenerateProjectFiles.bat is failed to find! [{file_path}]"
            )
            return

        # exceute GenerateProjectFiles.bat
        execute_powershell_content(f"{file_path}", True)


class BaseDescriptor:
    def __init__(self):
        self.json_object = {}


class PluginDescriptor(BaseDescriptor):
    def __init__(self, plugin_name):
        super().__init__()

        self.plugin_name = plugin_name
        self.json_object.setdefault("FileVersion", 3)
        self.json_object.setdefault("Version", 1)
        self.json_object.setdefault("VersionName", "1.0")
        self.json_object.setdefault("FriendlyName", self.plugin_name)
        self.json_object.setdefault("Category", "Beaver Lab")
        self.json_object.setdefault("EnabledByDefault", False)
        self.json_object.setdefault("CanContainContent", True)

    def save(self, dir: str):
        file_name = f"{self.plugin_name}.uplugin"
        file_path = os.path.join(dir, file_name)
        write_json_data(self.json_object, file_path)


class PluginGenerator(SourceGenerator):
    def __init__(self, plugin_name: str, plugin_directory: str):
        super().__init__(plugin_name, plugin_directory)

    def generate(self):
        # generate directory (if exists, remove directory and re-create directory)
        if os.path.isdir(self.directory):
            shutil.rmtree(self.directory)
        os.mkdir(self.directory)

        # generate 'Source' folder
        source_folder_path = os.path.join(self.directory, "Source")
        os.mkdir(source_folder_path)

        # generate 'Content' folder
        content_folder_path = os.path.join(self.directory, "Content")
        os.mkdir(content_folder_path)

        # generate 'Config'
        config_folder_path = os.path.join(self.directory, "Config")
        os.mkdir(config_folder_path)

        # generate .uplugin file
        plugin_descriptor = PluginDescriptor(self.name)
        plugin_descriptor.save(self.directory)

        # execute GenerateProjectFile.bat
        super().execute_generated_project_files()


# Unreal Build.cs file's string template
build_cs_template = """
using UnrealBuildTool;

public class ${ModuleName} : ModuleRules
{
    public ${ModuleName}(ReadOnlyTargetRules Target) : base(Target)
    {
        PublicDependencyModuleNames.AddRange(
			new string[]
            {
                "Core",
                "CoreUObject"
            });

        PrivateDependencyModuleNames.AddRange(
            new string[]
            {
                
            });

        PublicIncludePaths.AddRange(
			new string[]
            {
                
            });

        PrivateIncludePaths.AddRange(
            new string[]
            {
                
            });        
    }
}
"""

# Unreal module cpp string template
module_cpp_template = """
#include "${ModuleName}.h"

#define LOCTEXT_NAMESPACE "${ModuleName}"

DEFINE_LOG_CATEGORY(${ModuleName})

IMPLEMENT_MODULE(F${ModuleName}Module, ${ModuleName});

void F${ModuleName}Module::StartupModule()
{
	UE_LOG(${ModuleName}, Log, TEXT("F${ModuleName}Module: Log Started"));
}

void F${ModuleName}Module::ShutdownModule()
{
	UE_LOG(${ModuleName}, Log, TEXT("F${ModuleName}Module: Log Ended"));
}

#undef LOCTEXT_NAMESPACE
"""

# unreal  module header string template
module_header_template = """
#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(${ModuleName}, All, All)

class F${ModuleName}Module : public FDefaultModuleImpl
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
"""


class ModuleGenerator(SourceGenerator):
    def __init__(self, module_name: str, module_directory: str):
        super().__init__(module_name, module_directory)

    def generate(self):
        # create directory
        if os.path.isdir(self.directory):
            shutil.rmtree(self.directory)
        os.mkdir(self.directory)

        # create conversions
        conversions = dict(ModuleName=self.name)

        # generate build.cs file
        build_cs = Template(build_cs_template)
        build_cs = build_cs.safe_substitute(conversions)

        cs_file_path = f"{self.name}.Build.cs"
        cs_file_path = os.path.join(self.directory, cs_file_path)

        with open(cs_file_path, "w+") as content:
            content.writelines(build_cs)

        # generate Public/Private folders
        public_directory = os.path.join(self.directory, "Public")
        os.mkdir(public_directory)
        os.mkdir(os.path.join(self.directory, "Private"))

        # generate module cpp files (.h/.cpp)
        header_file_path = f"{self.name}.h"
        header_file_path = os.path.join(public_directory, header_file_path)

        cpp_file_path = f"{self.name}.cpp"
        cpp_file_path = os.path.join(public_directory, cpp_file_path)

        module_header = Template(module_header_template)
        module_cpp = Template(module_cpp_template)

        module_header = module_header.safe_substitute(conversions)
        module_cpp = module_cpp.safe_substitute(conversions)

        with open(header_file_path, "w+") as content:
            content.writelines(module_header)

        with open(cpp_file_path, "w+") as content:
            content.writelines(module_cpp)

        # generate project files
        self.execute_generated_project_files()


actor_class_header_template = """
#pragma once

#include "CoreMinimal.h"
#include "UObject/ObjectMacros.h"
#include "GameFramework/Actor.h"

#include "${ClassName}.generated.h"

DECLARE_LOG_CATEGORY_EXTERN(${ClassName}, All, All)

UCLASS()
class A${ClassName} : public AActor
{
	GENERATED_UCLASS_BODY()
};
"""

actor_class_cpp_template = """
#include "${ClassName}.h"

#define LOCTEXT_NAMESPACE "${ClassName}"
DEFINE_LOG_CATEGORY(${ClassName})

//////////////////////////////////////////////////////////////////////////
// A${ClassName}

A${ClassName}::A${ClassName}(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{

}

void Test_${ClassName}(UWorld* InWorld, bool Next)
{
	
}

#undef LOCTEXT_NAMESPACE
"""

raw_class_header_template = """
#pragma once

#include "CoreMinimal.h"

DECLARE_LOG_CATEGORY_EXTERN(${ClassName}, All, All)

class F${ClassName}
{
public:	
};
"""

raw_class_cpp_template = """
#include "${ClassName}.h"

#define LOCTEXT_NAMESPACE "${ClassName}"
DEFINE_LOG_CATEGORY(${ClassName})

/////////////////////////////////////////////////////
// F${ClassName}

#undef LOCTEXT_NAMESPACE
"""

uobject_class_header_template = """
#pragma once

#include "CoreMinimal.h"
#include "UObject/ObjectMacros.h"
#include "UObject/UObject.h"
#include "${ClassName}.generated.h"

DECLARE_LOG_CATEGORY_EXTERN(${ClassName}, All, All)

UCLASS(MinimalAPI)
class U${ClassName} : public UObject
{
	GENERATED_UCLASS_BODY()
};
"""

uobject_class_cpp_template = """
#include "${ClassName}.h"

#define LOCTEXT_NAMESPACE "${ClassName}"
DEFINE_LOG_CATEGORY(${ClassName})

//////////////////////////////////////////////////////////////////////////
// U${ClassName}

U${ClassName}::U${ClassName}(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

#undef LOCTEXT_NAMESPACE
"""


class ClassGenerator(SourceGenerator):
    def __init__(
        self, class_type: UnrealClassType, class_name: str, class_directory: str
    ):
        super().__init__(class_name, class_directory)
        self.type = class_type

        # override directory again
        self.directory = class_directory

    def generate(self):
        # get header/cpp file path
        header_file_path = f"{self.name}.h"
        header_file_path = os.path.join(self.directory, header_file_path)
        if os.path.exists(header_file_path):
            shutil.rmtree(header_file_path)

        cpp_file_path = f"{self.name}.cpp"
        cpp_file_path = os.path.join(self.directory, cpp_file_path)
        if os.path.exists(cpp_file_path):
            shutil.rmtree(cpp_file_path)

        # get conversion set
        conversions = dict(ClassName=self.name)

        # get header/cpp content
        header_content = None
        cpp_content = None
        if self.type == UnrealClassType.RAW:
            header_content = Template(raw_class_header_template)
            cpp_content = Template(raw_class_cpp_template)
        elif self.type == UnrealClassType.UOBJECT:
            header_content = Template(uobject_class_header_template)
            cpp_content = Template(uobject_class_cpp_template)
        elif self.type == UnrealClassType.ACTOR:
            header_content = Template(actor_class_header_template)
            cpp_content = Template(actor_class_cpp_template)

        # safe convert content with class name
        header_content = header_content.safe_substitute(conversions)
        cpp_content = cpp_content.safe_substitute(conversions)

        # finally write the contents (.h/.cpp)
        with open(header_file_path, "w+") as content:
            content.writelines(header_content)
        with open(cpp_file_path, "w+") as content:
            content.writelines(cpp_content)

        # update the .vsproj
        self.execute_generated_project_files()


class UnrealCookContext(SingletonInstance):
    def __init__(self):
        # archive path (output directory to override)
        self.archive_path = None
        # map name: note that it has a form, "<Map0>+<Map1>+..."
        self.maps_arg = None


def unreal_build_cook_run():
    project_arg = UnrealEnvContext.instance().unreal_project_path
    archive_dir_arg = UnrealCookContext.instance().archive_path

    if project_arg == None or archive_dir_arg == None:
        Logger.instance().info(
            f"argument is wrong [project arg: {project_arg}][archive_dir_arg: {archive_dir_arg}]"
        )
        return

    # try to find AutomationTool.exe from unreal_path
    unreal_engine_path = UnrealEnvContext.instance().unreal_path
    automation_tool_path = os.path.join(
        unreal_engine_path, "Engine", "Binaries", "DotNET", "AutomationTool.exe"
    )
    automation_tool_path = os.path.normpath(automation_tool_path)
    if not os.path.exists(automation_tool_path):
        Logger.instance().info(
            f"automation tool binary doesn't exists [{automation_tool_path}]"
        )
        return

    # construct cmd
    command_args = [
        f"{automation_tool_path}",
        "BuildCookRun",
        f'-project="{project_arg}"',
        "-noP4",
        "-platform=Win64",
        "-clientconfig=Development",
        "-serverconfig=Development",
        "-cook",
        "-compressed",
        "-server",
        "-serverplatform=Win64",
        "-build",
        "-stage",
        "-pak",
        "-bvpak",
        "-archive",
        f'-archivedirectory="{archive_dir_arg}"',
        "-iterate",
        "-utf8output",
    ]

    """add additional arguments"""
    # map argument
    maps_arg = UnrealCookContext.instance().maps_arg
    if maps_arg != None:
        command_args.append(f"-Map={maps_arg}")

    # leave the log
    """
    with open("unreal_cook.log", "w", encoding="utf-8") as f:
        # execute the automationtool.exe with command_args
        output = subprocess.Popen(command_args, stdout=subprocess.PIPE)
        while True:
            line = output.stdout.readline()
            if not line:
                break
            formatted_line = line.decode("utf-8")
            f.write(formatted_line)

    # block until it finished
    output.communicate()
    """

    """write batch files"""
    # server batch file
    # we need make server batch files for maps (each map needs one separate batch file)
    maps = maps_arg.split("+")
    for map in maps:
        # get the base name of map
        map = map.split("/")[-1]
        server_bat_file_path = os.path.join(archive_dir_arg, f"Server_{map}.bat")
        with open(server_bat_file_path, "w+") as bat_file:
            bat_file.write(
                f"start .\WindowsServer\CowboyServer.exe {map} -server -game -log -fullcrashdumpalways -noailogging -NOVERIFYGC -NOSTEAM"
            )

    # client batch file
    client_bat_file_path = os.path.join(archive_dir_arg, f"Client_LocalHost.bat")
    with open(client_bat_file_path, "w+") as bat_file:
        bat_file.write(
            "start .\WindowsNoEditor\Cowboy.exe 127.0.0.1 -game -noailogging -NOVERIFYGC -NOSTEAM"
        )


"""
    DearPyGui UI functions
"""


def SGDUnreal_project_setup():
    # get parent tag
    parent_tag = DearPyGuiApp.instance().primary_window_tag

    # input_text variables
    unreal_src_path_input_text = None
    unreal_project_path_input_text = None
    plugin_path_input_text = None
    generate_project_file_path_input_text = None
    generate_project_files_path_input_text = None

    # set width/height for each row
    row_width = 450
    row_height = 30

    # SGDUnreal Project Setup header
    with dpg.collapsing_header(label="SGDUnreal Project Setup", parent=parent_tag):
        # set label width
        label_width = 30

        # set hoizontal spacing
        horizontal_spacing = 2

        # set fixed height for this setup
        child_window_height = row_height * 5
        with dpg.child_window(autosize_x=True, height=child_window_height):
            # row 0
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Unreal Source Path
                content = "Unreal Source Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_unreal_src_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]
                    if file_path_name != None:
                        UnrealEnvContext.instance().setup(file_path_name)
                        # update input text
                        dpg.set_value(
                            unreal_src_path_input_text,
                            UnrealEnvContext.instance().unreal_path,
                        )
                        dpg.set_value(
                            plugin_path_input_text,
                            UnrealEnvContext.instance().curr_working_plugin_path,
                        )
                        dpg.set_value(
                            generate_project_file_path_input_text,
                            UnrealEnvContext.instance().generate_project_file_path,
                        )

                callback_function = FunctionObject(
                    on_clicked_unreal_src_path_file_dialog
                )
                unreal_src_path_input_text = input_text_search_directory_module(
                    callback_function,
                    remaining_space,
                    horizontal_spacing,
                )
                if UnrealEnvContext.instance().unreal_path != None:
                    dpg.set_value(
                        unreal_src_path_input_text,
                        UnrealEnvContext.instance().unreal_path,
                    )

            # row 1
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Unreal Project Path (.uproject)
                content = "Unreal Project Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_unreal_project_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]

                    def on_clicked_unreal_project_path_file_dialog_internal(
                        file_path_name: str,
                    ):
                        if file_path_name != None:
                            basename = os.path.basename(file_path_name)
                            basename_ext = os.path.splitext(basename)[1]
                            if basename_ext == ".uproject":
                                # update unreal_project_path
                                UnrealEnvContext.instance().unreal_project_path = (
                                    file_path_name
                                )
                                # update input text
                                dpg.set_value(
                                    unreal_project_path_input_text,
                                    UnrealEnvContext.instance().unreal_project_path,
                                )

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(
                            FunctionObject(
                                on_clicked_unreal_project_path_file_dialog_internal,
                                file_path_name,
                            )
                        )
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                callback_function = FunctionObject(
                    on_clicked_unreal_project_path_file_dialog
                )
                unreal_project_path_input_text = input_text_search_directory_module(
                    callback_function,
                    remaining_space,
                    horizontal_spacing,
                    is_directory_only=False,
                )
                if UnrealEnvContext.instance().unreal_project_path != None:
                    dpg.set_value(
                        unreal_project_path_input_text,
                        UnrealEnvContext.instance().unreal_project_path,
                    )

            # row 2
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Plugin Path
                content = "Plugin Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing
                with dpg.group(horizontal=True, horizontal_spacing=2):
                    plugin_path_input_text = dpg.add_input_text(
                        readonly=True, width=remaining_space
                    )
                    if UnrealEnvContext.instance().curr_working_plugin_path != None:
                        dpg.set_value(
                            plugin_path_input_text,
                            UnrealEnvContext.instance().curr_working_plugin_path,
                        )
            # row 3
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # GenerateProjectFiles Path
                content = "GenerateProjectFiles.bat: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_generate_project_files_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]

                    def on_clicked_generate_project_files_path_file_dialog_internal(
                        file_path_name: str,
                    ):
                        if file_path_name != None:
                            basename = os.path.basename(file_path_name)
                            basename_ext = os.path.splitext(basename)[1]
                            if basename_ext == ".bat":
                                # update generate_project_file_path
                                UnrealEnvContext.instance().generate_project_file_path = (
                                    file_path_name
                                )
                                # update input text
                                dpg.set_value(
                                    generate_project_files_path_input_text,
                                    UnrealEnvContext.instance().generate_project_file_path,
                                )

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(
                            FunctionObject(
                                on_clicked_generate_project_files_path_file_dialog_internal,
                                file_path_name,
                            )
                        )
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                callback_function = FunctionObject(
                    on_clicked_generate_project_files_path_file_dialog
                )
                generate_project_files_path_input_text = (
                    input_text_search_directory_module(
                        callback_function,
                        remaining_space,
                        horizontal_spacing,
                        is_directory_only=False,
                    )
                )
                if UnrealEnvContext.instance().generate_project_file_path != None:
                    dpg.set_value(
                        generate_project_files_path_input_text,
                        UnrealEnvContext.instance().generate_project_file_path,
                    )
            # row 4
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, horizontal_spacing=0):

                def update_unreal_env_json_settings():
                    UnrealEnvContext.instance().update_settings()

                dpg.add_spacer(width=500)
                dpg.add_button(
                    label="UPDATE",
                    width=135,
                    height=25,
                    callback=update_unreal_env_json_settings,
                )


def programmer_assistant_setup():
    # get parent tag
    parent_tag = DearPyGuiApp.instance().primary_window_tag

    # set width/height for each row
    row_width = 450
    row_height = 30

    # set label_width
    label_width = 20

    # set hoizontal spacing
    horizontal_spacing = 2

    # input_text attributes
    plugin_name_input_text = None
    plugin_path_input_text = None

    module_name_input_text = None
    module_path_input_text = None

    class_name_input_text = None
    class_path_input_text = None

    # programmer assistant setup
    with dpg.collapsing_header(label="Unreal Programmer Assistant", parent=parent_tag):
        # calculate child window height
        child_window_height = row_height * 4
        with dpg.child_window(autosize_x=True, height=child_window_height):
            # plugin name (row 1)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Plugin Name
                content = "Plugin Name: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing
                with dpg.group(horizontal=True, horizontal_spacing=horizontal_spacing):
                    # callback when plugin name is changed
                    def on_changed_plugin_name(sender, app_data):
                        UnrealProgrammerAssistantContext.instance().plugin_name = (
                            app_data
                        )

                    plugin_name_input_text = dpg.add_input_text(
                        width=remaining_space,
                        callback=on_changed_plugin_name,
                    )
            # plugin path (row 2)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Plugin Path
                content = "Plugin Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_plugin_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]
                    if file_path_name != None:
                        UnrealProgrammerAssistantContext.instance().plugin_path = (
                            file_path_name
                        )
                        # update input text
                        dpg.set_value(
                            plugin_path_input_text,
                            UnrealProgrammerAssistantContext.instance().plugin_path,
                        )

                callback_function = FunctionObject(on_clicked_plugin_path_file_dialog)
                plugin_path_input_text = input_text_search_directory_module(
                    callback_function,
                    remaining_space,
                    horizontal_spacing,
                )
            # Apply button (row 3)
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, horizontal_spacing=0):

                def generate_plugin():
                    def generate_plugin_internal():
                        plugin_name = (
                            UnrealProgrammerAssistantContext.instance().plugin_name
                        )
                        plugin_path = (
                            UnrealProgrammerAssistantContext.instance().plugin_path
                        )

                        if not os.path.isdir(plugin_path):
                            Logger.instance().info(
                                f"[ERROR] failed to find plugin path! [{plugin_path}]"
                            )
                            return

                        plugin_generator = PluginGenerator(plugin_name, plugin_path)
                        plugin_generator.generate()

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(FunctionObject(generate_plugin_internal))
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                dpg.add_spacer(width=441)
                dpg.add_button(
                    label="GENERATE",
                    width=135,
                    height=25,
                    callback=generate_plugin,
                )

        # row 2 - Module
        with dpg.child_window(autosize_x=True, height=child_window_height):
            # module name (row 1)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Module Name
                content = "Module Name: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing
                with dpg.group(horizontal=True, horizontal_spacing=horizontal_spacing):
                    # callback when module name is changed
                    def on_changed_module_name(sender, app_data):
                        UnrealProgrammerAssistantContext.instance().module_name = (
                            app_data
                        )

                    module_name_input_text = dpg.add_input_text(
                        width=remaining_space,
                        callback=on_changed_module_name,
                    )
            # module path (row 2)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Module Path
                content = "Module Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_module_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]
                    if file_path_name != None:
                        UnrealProgrammerAssistantContext.instance().module_path = (
                            file_path_name
                        )
                        # update input text
                        dpg.set_value(
                            module_path_input_text,
                            UnrealProgrammerAssistantContext.instance().module_path,
                        )

                callback_function = FunctionObject(on_clicked_module_path_file_dialog)
                module_path_input_text = input_text_search_directory_module(
                    callback_function,
                    remaining_space,
                    horizontal_spacing,
                )

            # Radios & Generate button (row 3)
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, horizontal_spacing=0):
                # button
                def generate_module():
                    def generate_module_internal():
                        module_name = (
                            UnrealProgrammerAssistantContext.instance().module_name
                        )
                        module_path = (
                            UnrealProgrammerAssistantContext.instance().module_path
                        )

                        if not os.path.isdir(module_path):
                            Logger.instance().info(
                                f"[ERROR] failed to find module path! [{module_path}]"
                            )
                            return

                        module_generator = ModuleGenerator(module_name, module_path)
                        module_generator.generate()

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(FunctionObject(generate_module_internal))
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                dpg.add_spacer(width=441)
                dpg.add_button(
                    label="GENERATE",
                    width=135,
                    height=25,
                    callback=generate_module,
                )

        # row 3 - Class
        with dpg.child_window(autosize_x=True, height=child_window_height):
            # class name (row 1)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Class Name
                content = "Class Name: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing
                with dpg.group(horizontal=True, horizontal_spacing=horizontal_spacing):
                    # callback when class name is changed
                    def on_changed_class_name(sender, app_data):
                        UnrealProgrammerAssistantContext.instance().class_name = (
                            app_data
                        )

                    class_name_input_text = dpg.add_input_text(
                        width=remaining_space,
                        callback=on_changed_class_name,
                    )
            # class path (row 2)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # Class Path
                content = "Class Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_class_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]
                    if file_path_name != None:
                        UnrealProgrammerAssistantContext.instance().class_path = (
                            file_path_name
                        )
                        # update input text
                        dpg.set_value(
                            class_path_input_text,
                            UnrealProgrammerAssistantContext.instance().class_path,
                        )

                callback_function = FunctionObject(on_clicked_class_path_file_dialog)
                class_path_input_text = input_text_search_directory_module(
                    callback_function,
                    remaining_space,
                    horizontal_spacing,
                )

            # Apply button (row 3)
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, horizontal_spacing=0):
                # radio
                def select_class_type(sender, app_data):
                    class_type: UnrealClassType = (
                        UnrealProgrammerAssistantContext.instance().class_type
                    )
                    if app_data == "Raw":
                        class_type = UnrealClassType.RAW
                    elif app_data == "UObject":
                        class_type = UnrealClassType.UOBJECT
                    elif app_data == "Actor":
                        class_type = UnrealClassType.ACTOR

                    def select_class_type_internal(class_type: UnrealClassType):
                        UnrealProgrammerAssistantContext.instance().class_type = (
                            class_type
                        )

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(
                            FunctionObject(
                                select_class_type_internal,
                                class_type,
                            )
                        )
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                dpg.add_radio_button(
                    ("Raw", "UObject", "Actor"),
                    callback=select_class_type,
                    horizontal=True,
                )

                def generate_class():
                    def generate_class_internal():
                        class_name = (
                            UnrealProgrammerAssistantContext.instance().class_name
                        )
                        class_path = (
                            UnrealProgrammerAssistantContext.instance().class_path
                        )
                        class_type = (
                            UnrealProgrammerAssistantContext.instance().class_type
                        )

                        if not os.path.isdir(class_path):
                            Logger.instance().info(
                                f"[ERROR] failed to find module path! [{class_path}]"
                            )
                            return

                        class_generator = ClassGenerator(
                            class_type, class_name, class_path
                        )
                        class_generator.generate()

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(FunctionObject(generate_class_internal))
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                dpg.add_spacer(width=251)
                dpg.add_button(
                    label="GENERATE",
                    width=135,
                    height=25,
                    callback=generate_class,
                )


def cooking_assistant_setup():
    # get parent tag
    parent_tag = DearPyGuiApp.instance().primary_window_tag

    # set width/height for each row
    row_width = 450
    row_height = 30

    # set label_width
    label_width = 20

    # set hoizontal spacing
    horizontal_spacing = 2

    # input_text attributes
    archive_path_input_text = None
    maps_arg_input_text = None

    # programmer assistant setup
    with dpg.collapsing_header(label="Cooker Assistant", parent=parent_tag):
        # calculate child window height
        child_window_height = row_height * 4
        with dpg.child_window(autosize_x=True, height=child_window_height):
            # archive path (row 1)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # archive path
                content = "Archive Path: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing

                def on_clicked_archive_path_file_dialog(*args, **kwargs):
                    file_path_name = kwargs["file_path"]
                    if file_path_name != None:
                        UnrealCookContext.instance().archive_path = file_path_name
                        # update input text
                        dpg.set_value(
                            archive_path_input_text,
                            UnrealCookContext.instance().archive_path,
                        )

                callback_function = FunctionObject(on_clicked_archive_path_file_dialog)
                archive_path_input_text = input_text_search_directory_module(
                    callback_function,
                    remaining_space,
                    horizontal_spacing,
                )
            # maps arg (row 2)
            with dpg.group(horizontal=True):
                remaining_space = row_width
                # maps arg
                content = "Map Arguments: "
                content = f"{content:<{label_width}}"
                dpg.add_text(content)
                remaining_space = remaining_space - label_width - horizontal_spacing
                with dpg.group(horizontal=True, horizontal_spacing=horizontal_spacing):
                    # callback when maps arg is changed
                    def on_changed_maps_arg(sender, app_data):
                        UnrealCookContext.instance().maps_arg = app_data

                    maps_arg_input_text = dpg.add_input_text(
                        width=remaining_space,
                        callback=on_changed_maps_arg,
                    )
            # Apply button (row 3)
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, horizontal_spacing=0):

                def generate_plugin():
                    def generate_plugin_internal():
                        unreal_build_cook_run()

                    event_task = EventTask()
                    event_task.add_command(
                        EventCommand(FunctionObject(generate_plugin_internal))
                    )
                    DearPyGuiApp.instance().add_task(event_task)

                dpg.add_spacer(width=441)
                dpg.add_button(
                    label="COOK",
                    width=135,
                    height=25,
                    callback=generate_plugin,
                )
