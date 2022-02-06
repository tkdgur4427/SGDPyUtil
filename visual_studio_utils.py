import os
import SGDPyUtil.winreg_utils as winreg_utils

def get_visual_studio_version() -> str:
    vs_ver_mapper = {
        "16.0": "2019",
    }

    common_key_path = "\Microsoft\VisualStudio\%s"
    possible_vs_versions = [
        "16.0",  # visual studio 2019
    ]
    installed_vs_versions = []
    for version in possible_vs_versions:
        key_suffix = common_key_path % version
        if winreg_utils.try_read_registry_key(key_suffix):
            installed_vs_versions.append(version)

    vs_version = installed_vs_versions[0] if len(installed_vs_versions) else None
    vs_version = vs_ver_mapper.get(vs_version, None)

    return vs_version


def get_visual_studio_path(vs_version: str) -> str:
    """
    recommand to use like: get_visual_studio_path(get_visual_studio_version())
    @param vs_version: visual studio version like '2015', '2019'
    """
    vs_path = (
        f"C:\Program Files (x86)\Microsoft Visual Studio\{vs_version}\Professional"
    )
    if not os.path.isdir(vs_path):
        vs_path = None
    return vs_path


def get_msbuild_path(vs_version: str, has_exe: bool = False) -> str:
    msbuild_path = f"C:\Program Files (x86)\Microsoft Visual Studio\{vs_version}\Professional\MSBuild\Current\Bin"
    msbuild_exe_path = os.path.join(msbuild_path, "msbuild.exe")

    if not os.path.exists(msbuild_exe_path):
        msbuild_path = None
        msbuild_exe_path = None

    return msbuild_path if not has_exe else msbuild_exe_path
