from distutils.util import execute
import os
import platform
import shutil
import zipfile
import tarfile
import ssl
import hashlib
import urllib
import getopt
import traceback

from SGDPyUtil.singleton_utils import SingletonInstance
from SGDPyUtil.logging_utils import Logger
from SGDPyUtil.powershell_utils import execute_command
from SGDPyUtil.visual_studio_utils import *
from SGDPyUtil.main import *
from SGDPyUtil.json_utils import *

try:
    from urllib.request import urlparse
    from urllib.request import urlunparse
    from urllib.request import urlretrieve
    from urllib.request import quote
except ImportError:
    from urlparse import urlparse
    from urlparse import urlunparse
    from urllib import urlretrieve
    from urllib import URLopener
    from urllib import quote

try:
    import paramiko
    import scp

    scp_available = True
except:
    scp_available = False
    Logger.instance().info(
        f"[WARNING] please install the Python packages [paramiko, scp] for full script operation"
    )


class BootstrapGlobal(SingletonInstance):
    def __init__(self):
        # system
        self.system = platform.system()

        # base directory
        self.SRC_DIR_BASE = "src"
        self.ARCHIVE_DIR_BASE = "archives"
        self.SNAP_SHOT_DIR_BASE = "snapshot"

        # properties
        self.DEFAULT_PNUM = 3
        self.DEBUG_OUTPUT = False
        self.FALLBACK_URL = ""
        self.USE_TAR = False
        self.USE_UNZIP = False

        # TOOL_COMMAND
        self.TOOL_COMMAND_PYTHON = "python" if self.system == "Windows" else "python3"
        self.TOOL_COMMAND_GIT = "git"
        self.TOOL_COMMAND_SVN = "svn"
        self.TOOL_COMMAND_PATCH = "patch"
        self.TOOL_COMMAND_TAR = "tar"
        self.TOOL_COMMAND_UNZIP = "unzip"

        return

    def setup(self, base_directory: str):
        """redirect directory based on base_directory"""
        self.BASE_DIR = base_directory
        self.SRC_DIR = os.path.join(self.BASE_DIR, self.SRC_DIR_BASE)
        self.ARCHIVE_DIR = os.path.join(self.BASE_DIR, self.ARCHIVE_DIR_BASE)
        self.SNAPSHOT_DIR = os.path.join(self.BASE_DIR, self.SNAP_SHOT_DIR_BASE)

        return


def die_if_non_zero(res):
    if res != 0:
        raise ValueError(f"command returns non-zero status: {str(res)}")


def escapify_path(path: str) -> str:
    if path.find(" ") == -1:
        return path
    if BootstrapGlobal.instance().system == "Windows":
        return f'"{path}"'
    return path.replace("\\", " ")


def clone_repository(
    type: str,
    url: str,
    target_name: str,
    revision=None,
    try_only_local_operation: bool = False,
):
    target_dir = escapify_path(
        os.path.join(BootstrapGlobal.instance().SRC_DIR, target_name)
    )
    target_dir_exists = os.path.exists(target_dir)
    Logger.instance().info(f"[LOG] cloning {url} to {target_dir}")

    if type == "git":
        repo_exists = os.path.exists(os.path.join(target_dir, ".git"))
        git_command = BootstrapGlobal.instance().TOOL_COMMAND_GIT

        if not repo_exists:
            if try_only_local_operation:
                raise RuntimeError(
                    f"repository for {target_name} not found; cannot execute local operation only"
                )
            if target_dir_exists:
                Logger.instance().info(
                    f"[LOG] removing directory {target_dir} before cloning"
                )
                shutil.rmtree(target_dir)
            die_if_non_zero(
                execute_command(f"{git_command} clone --recursive {url} {target_dir}")
            )
        elif not try_only_local_operation:
            Logger.instance().info(
                f"[LOG] repository already exists; fetching instead of cloning"
            )
            die_if_non_zero(
                execute_command(
                    f"{git_command} -C {target_dir} fetch --recurse-submodules"
                )
            )

        if revision is None:
            revision = "HEAD"

        die_if_non_zero(
            execute_command(f"{git_command} -C {target_dir} reset --hard {revision}")
        )
        die_if_non_zero(execute_command(f"{git_command} -C {target_dir} clean -fxd"))
    else:
        raise ValueError(f"cloning {type} repositories not implemented")
    return


def extract_file(filename: str, target_dir: str):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    system = BootstrapGlobal.instance().system

    Logger.instance().info(f"[LOG] extracting file {filename}")
    stem, extension = os.path.splitext(os.path.basename(filename))

    if extension == ".zip" or extension == "":
        zfile = zipfile.ZipFile(filename)
        extract_dir = os.path.commonprefix(zfile.namelist())

        has_folder = False
        for fname in zfile.namelist():
            if fname.find("/") != -1:
                has_folder = True

        extract_dir_local = ""
        if not has_folder:
            extract_dir = ""
        if extract_dir == "":
            extract_dir, extension2 = os.path.splitext(os.path.basename(filename))
            extract_dir_local = extract_dir

        extract_dir_abs = os.path.join(
            BootstrapGlobal.instance().SRC_DIR, extract_dir_local
        )

        try:
            os.makedirs(extract_dir_abs)
        except:
            pass

        if not BootstrapGlobal.instance().USE_UNZIP:
            zfile.extractall(extract_dir_abs)
            zfile.close()
        else:
            zfile.close()
            die_if_non_zero(
                execute_command(
                    f"{BootstrapGlobal.instance().TOOL_COMMAND_UNZIP} {filename} -d {extract_dir_abs}"
                )
            )

    else:
        raise RuntimeError(f"unknown compressed file format {extension}")

    if system == "Windows":
        extract_dir = extract_dir.replace("/", "\\")
        target_dir = target_dir.replace("/", "\\")
        if extract_dir[-1:] == "\\":
            extract_dir = extract_dir[:-1]

    # rename extracted folder to target_dir
    extract_dir_abs = os.path.join(BootstrapGlobal.instance().SRC_DIR, extract_dir)

    need_rename: bool = True
    if system == "Windows":
        need_rename = extract_dir_abs.lower() != target_dir.lower()

    if need_rename:
        os.rename(extract_dir_abs, target_dir)

    return


def create_archive_from_directory(
    src_dir_name: str, archive_name: str, delete_existing_archive=False
):
    if delete_existing_archive and os.path.exists(archive_name):
        Logger.instance().info(
            f"[LOG] removing snapshot file {archive_name} before creating new one"
        )
        os.remove(archive_name)

    archive_dir = os.path.dirname(archive_name)
    if not os.path.isdir(archive_dir):
        os.mkdir(archive_dir)

    with tarfile.open(archive_name, "w:gz") as tar:
        tar.add(src_dir_name, arcname=os.path.basename(src_dir_name))


# when this error occurs [<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:777)>]
# by PEP 467, all http comm should provide certificate and hostname
# if you set _create_unverified_context, we can by-pass!
ssl._create_default_https_context = ssl._create_unverified_context


def download_scp(hostname: str, username: str, path: str, target_dir: str):
    if not scp_available:
        error_msg = "missing python package [paramiko, scp]; cannot continue"
        Logger.instance().info(f"[ERROR] {error_msg}")
        raise RuntimeError(f"{error_msg}")

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(hostname=hostname, username=username)

    scpc = scp.SCPClient(ssh.get_transport())
    scpc.get(path, local_path=target_dir)


def compute_file_hash(filename: str):
    blocksize = 65536
    hasher = hashlib.sha1()
    with open(filename, "rb") as afile:
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
    return hasher.hexdigest()


def download_file(
    url: str,
    download_dir: str,
    sha1_hash=None,
    force_download=False,
    user_agent=False,
):
    if not os.path.isdir(download_dir):
        os.mkdir(download_dir)

    p = urlparse(url)
    url = urlunparse(
        [p[0], p[1], quote(p[2]), p[3], p[4], p[5]]
    )  # replace special characters in the URL path

    filename_rel = os.path.split(p.path)[1]
    target_filename = os.path.join(download_dir, filename_rel)

    # check SHA1 hash, if file already exists
    if os.path.exists(target_filename) and sha1_hash is not None and sha1_hash != "":
        hash_file = compute_file_hash(target_filename)
        if hash_file != sha1_hash:
            Logger.instance().info(
                f"[WARNING] hash of {target_filename} ({hash_file}) does not match expected hash ({sha1_hash}); forcing download"
            )
            force_download = True

    # download file
    if (not os.path.exists(target_filename)) or force_download:
        Logger.instance().info(f"[LOG] downloading {url} to {target_filename}")
        if p.scheme == "ssh":
            download_scp(p.hostname, p.username, p.path, download_dir)
        else:
            if user_agent is not None:
                opener = urllib.request.build_opener()
                opener.addheaders = [("User-agent", user_agent)]
                f = open(target_filename, "wb")
                f.write(opener.open(url).read())
                f.close()
            else:
                urlretrieve(url, target_filename)
    else:
        Logger.instance().info(f"[LOG] skipping download of {url}; already downloaded")

    # check sha1 hash
    if sha1_hash is not None and sha1_hash != "":
        hash_file = compute_file_hash(target_filename)
        if hash_file != sha1_hash:
            raise RuntimeError(
                f"hash of {target_filename} ({hash_file}) differs from expected hash ({sha1_hash})"
            )

    return target_filename


def download_and_extract_file(
    url,
    download_dir,
    target_dir_name,
    sha1_hash=None,
    force_download=False,
    user_agent=None,
):
    target_filename = download_file(
        url, download_dir, sha1_hash, force_download, user_agent
    )
    extract_file(
        target_filename,
        os.path.join(BootstrapGlobal.instance().SRC_DIR, target_dir_name),
    )
    return


def generate_include_header_only(repo_path: str, src_folder_name: str):
    # if src_folder_name is ".", it means root repository
    is_root = False if src_folder_name != "." else True

    # get src_path
    src_path = repo_path
    if not is_root:
        src_path = os.path.join(src_path, src_folder_name)
    src_path = os.path.normpath(src_path)

    # get dst_path
    dst_path = os.path.join(repo_path, "include")
    if not is_root:
        dst_path = os.path.join(dst_path, src_folder_name)
    dst_path = os.path.normpath(dst_path)

    # delete and re-create dst path
    if os.path.isdir(dst_path):
        shutil.rmtree(dst_path)
    os.makedirs(dst_path)

    for root, _, files in os.walk(src_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            # filter header file type (c++)
            if ext == ".h" or ext == ".hpp" or ext == ".inl" or ext == ".cpp":
                # get src_file_path
                src_file_path = os.path.join(root, file)
                src_file_path = os.path.normpath(src_file_path)

                # get dst_file_path
                commonprefix = os.path.commonprefix([src_path, src_file_path])
                base_dst_file_path = src_file_path[len(commonprefix) :]
                if base_dst_file_path.startswith("\\"):
                    base_dst_file_path = base_dst_file_path[len("\\") :]
                dst_file_path = os.path.join(dst_path, base_dst_file_path)
                dst_file_path = os.path.normpath(dst_file_path)

                # get dst_file_dir
                dst_file_dir = os.path.dirname(dst_file_path)

                # try to make dir
                os.makedirs(dst_file_dir, exist_ok=True)

                # copy target header
                shutil.copy2(src_file_path, dst_file_path)

    return


def generate_lib_by_cmake(repo_path: str, src_folder_name: str, cmake_cmd_args: str):
    # create dst_path
    dst_path = os.path.join(repo_path, "lib")
    if not os.path.isdir(dst_path):
        os.mkdir(dst_path)

    # check whether we already create .lib by checking .build.lib.success.txt's existance
    verify_mark_file_path = os.path.join(dst_path, ".build.lib.success.txt")
    if os.path.exists(verify_mark_file_path):
        return

    # generate build folder (visual studio project file generation)
    cmake_cmd = "cmake"
    cmake_cmd = f"{cmake_cmd} -S . -B build {cmake_cmd_args}"
    execute_command(cmake_cmd, True, repo_path)

    # get ALL_BUILD.vxcproj path
    build_path = os.path.join(repo_path, "build")
    vcxproj_path = os.path.join(build_path, "ALL_BUILD.vcxproj")

    # get msbuild path
    msbuild_path = get_msbuild_path(get_visual_studio_version())
    build_cmd = "msbuild"

    # build .vcxproj files
    build_cmd_debug = f"{build_cmd} {vcxproj_path} /p:configuration=Debug"
    build_cmd_release = f"{build_cmd} {vcxproj_path} /p:configuration=Release"

    execute_command(build_cmd_debug, True, msbuild_path)
    execute_command(build_cmd_release, True, msbuild_path)

    # move generated .lib to folder lib
    lib_path = os.path.join(build_path, src_folder_name)
    lib_debug_path = os.path.join(lib_path, "Debug")
    lib_release_path = os.path.join(lib_path, "Release")

    # process Debug
    dst_debug_path = os.path.join(dst_path, "Debug")
    if not os.path.isdir(dst_debug_path):
        os.mkdir(dst_debug_path)
    copytree(lib_debug_path, dst_debug_path)

    # process Release
    dst_release_path = os.path.join(dst_path, "Release")
    if not os.path.isdir(dst_release_path):
        os.mkdir(dst_release_path)
    copytree(lib_release_path, dst_release_path)

    # delete build folder
    shutil.rmtree(build_path)

    # mark lib build success by file
    mark_file_path = os.path.join(dst_path, ".build.lib.success.txt")
    # generate mark file
    with open(mark_file_path, "w") as mark_file:
        pass

    return


def log_libraries(data):
    for library in data:
        name = library.get("name", None)
        if name is not None:
            Logger.instance().info(f"[LOG] library name: {name}")


def print_options():
    print(
        "--------------------------------------------------------------------------------"
    )
    print("Downloads external libraries, and applies patches or scripts if necessary.")
    print("If the --name argument is not provided, all available libraries will be")
    print("downloaded.")
    print("")
    print("Options:")
    print("  --list, -l              List all available libraries")
    print("  --name, -n              Specifies the name of a single library to be")
    print("                          downloaded")
    print(
        "  --name-file, -N         Specifies a file that contains a (sub)set of libraries"
    )
    print(
        "                          to be downloaded. One library name per line; lines"
    )
    print("                          starting with '#' are considered comments.")
    print(
        "  --skip                  Specifies a name of a single library to be skipped"
    )
    print("  --clean, -c             Remove library directory before obtaining library")
    print(
        "  --clean-all, -C         Implies --clean, and also forces re-download of cached"
    )
    print("                          archive files")
    print(
        "  --base-dir, -b          Base directory, if script is called from outside of"
    )
    print("                          its directory")
    print(
        "  --bootstrap-file        Specifies the file containing the canonical bootstrap"
    )
    print("                          JSON data (default: bootstrap.json)")
    print(
        "  --local-bootstrap-file  Specifies the file containing local bootstrap JSON"
    )
    print(
        "                          data (e.g. for a particular project). The data in this"
    )
    print(
        "                          file will have higher precedence than the data from"
    )
    print("                          the canonical bootstrap file.")
    print("                          to extract tar archives")
    print(
        "  --use-unzip             Use 'unzip' command instead of Python standard library"
    )
    print("                          to extract zip archives")
    print(
        "  --repo-snapshots        Create a snapshot archive of a repository when its"
    )
    print("                          state changes, e.g. on a fallback location")
    print(
        "  --fallback-url          Fallback URL that points to an existing and already"
    )
    print(
        "                          bootstrapped `external` repository that may be used to"
    )
    print("                          retrieve otherwise unobtainable archives or")
    print("                          repositories. The --repo-snapshots option must be")
    print(
        "                          active on the fallback server. Allowed URL schemes are"
    )
    print("                          file://, ssh://, http://, https://, ftp://.")
    print(
        "  --force-fallback        Force using the fallback URL instead of the original"
    )
    print("                          sources")
    print("  --debug-output          Enables extra debugging output")
    print(
        "  --break-on-first-error  Terminate script once the first error is encountered"
    )
    print(
        "--------------------------------------------------------------------------------"
    )


def bootstrap_main(cwd: str, argv):
    # setup BootstrapGlobal
    BootstrapGlobal.instance().setup(cwd)

    # get cmd options with getopt
    try:
        opts, args = getopt.getopt(
            argv,
            "ln:n:cCb:h",
            [
                "list",
                "name=",
                "name-file=",
                "skip=",
                "clean",
                "clean-all",
                "base-dir",
                "bootstrap-file=",
                "local-bootstrap-file=",
                "use-unzip",
                "repo-snapshots",
                "fallback-url=",
                "force-fallback",
                "debug-output",
                "help",
                "break-on-first-error",
            ],
        )
    except getopt.GetoptError:
        print_options()
        return 0

    opt_names = []
    name_files = []
    skip_libs = []
    opt_clean = False
    opt_clean_archives = False
    list_libraries = False
    create_repo_snapshots = False

    # deps (dump as deps.json)
    deps_paths = []
    deps_libs = []

    BASE_DIR = BootstrapGlobal.instance().BASE_DIR
    SRC_DIR = BootstrapGlobal.instance().SRC_DIR
    ARCHIVE_DIR = BootstrapGlobal.instance().ARCHIVE_DIR
    SRC_DIR_BASE = BootstrapGlobal.instance().SRC_DIR_BASE
    ARCHIVE_DIR_BASE = BootstrapGlobal.instance().ARCHIVE_DIR_BASE
    SNAPSHOT_DIR_BASE = BootstrapGlobal.instance().SNAP_SHOT_DIR_BASE
    FALLBACK_URL = BootstrapGlobal.instance().FALLBACK_URL
    SNAPSHOT_DIR = BootstrapGlobal.instance().SNAPSHOT_DIR

    # get the system os info
    system = BootstrapGlobal.instance().system

    default_bootstrap_filename = "bootstrap.json"
    bootstrap_filename = os.path.abspath(
        os.path.join(BASE_DIR, default_bootstrap_filename)
    )
    local_bootstrap_filename = ""
    force_fallback = False
    break_on_first_error = False

    base_dir_path = ""

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print_options()
            return 0
        if opt in ("-l", "--list"):
            list_libraries = True
        if opt in ("-n", "--name"):
            opt_names.append(arg)
        if opt in ("-N", "--name-file"):
            name_files.append(os.path.abspath(arg))
        if opt in ("--skip"):
            skip_libs.append(arg)
        if opt in ("-c", "--clean"):
            opt_clean = True
        if opt in ("-C", "--clean-all"):
            opt_clean = True
            opt_clean_archives = True
        if opt in ("-b", "--base-dir"):
            base_dir_path = os.path.abspath(arg)
            BASE_DIR = base_dir_path
            SRC_DIR = os.path.join(BASE_DIR, SRC_DIR_BASE)
            ARCHIVE_DIR = os.path.join(BASE_DIR, ARCHIVE_DIR_BASE)
            bootstrap_filename = os.path.join(BASE_DIR, default_bootstrap_filename)
            Logger.instance().info(f"[LOG] using {arg} as base directory")
        if opt in ("--bootstrap-file",):
            bootstrap_filename = os.path.abspath(arg)
            Logger.instance().info(
                f"[LOG] using main bootstrap file {bootstrap_filename}"
            )
        if opt in ("--local_bootstrap-file",):
            local_bootstrap_filename = os.path.abspath(arg)
            Logger.instance().info(
                f"[LOG] using local bootstrap file {local_bootstrap_filename}"
            )
        if opt in ("--use-unzip",):
            USE_UNZIP = True
        if opt in ("--repo-snapshot",):
            create_repo_snapshots = True
            Logger.instance().info(f"[LOG] will create repository snapshots")
        if opt in ("--force-fallback",):
            force_fallback = True
            Logger.instance().info(f"[LOG] using fallback URL to fetch all libraries")
        if opt in ("--break-on-first-error",):
            break_on_first_error = True
        if opt in ("--debug-output",):
            DEBUG_OUTPUT = True

    if base_dir_path:
        os.chdir(base_dir_path)

    if name_files:
        for name_file in name_files:
            try:
                with open(name_file) as f:
                    opt_names_local = [l for l in (line.strip() for line in f) if l]
                    opt_names_local = [l for l in opt_names_local if l[0] != "#"]
                    opt_names += opt_names_local
            except:
                Logger.instance().info(f"[ERROR] cannot parse name file {name_file}")
                return -1

    if force_fallback and not FALLBACK_URL:
        Logger.instance().info(
            f"[Error] cannot force usage of the fallback location without specifying a fallback URL"
        )
        return -1

    state_filename = (
        os.path.join(
            os.path.dirname(os.path.splitext(bootstrap_filename)[0]),
            "." + os.path.basename(os.path.splitext(bootstrap_filename)[0]),
        )
        + os.path.splitext(bootstrap_filename)[1]
    )

    Logger.instance().info(f"[LOG] bootstrap_filename = {bootstrap_filename}")
    Logger.instance().info(f"[LOG] state_filename = {state_filename}")

    # read canonical libraries data
    data = read_json_data(bootstrap_filename)
    if data is None:
        return -1

    # some sanity checking
    for library in data:
        if library.get("name", None) is None:
            Logger.instance().info(
                f"[ERROR] invalid schema; library object does not have a 'name'"
            )
            return -1

    # read local libraries data, if available
    local_data = None
    if local_bootstrap_filename:
        local_data = read_json_data(local_bootstrap_filename)

        if local_data is None:
            return -1

        # some sanity checking
        for local_library in local_data:
            if local_library.get("name", None) is None:
                Logger.instance().info(
                    f"[ERROR] invalid schema; local library object does not have a 'name'"
                )
                return -1

    # merge canonical and local library data, if applicable; local libraries take procedence
    if local_data is not None:
        for local_library in local_data:
            local_name = local_library.get("name", None)
            found_canonical_library = False
            for n, library in enumerate(data):
                name = library.get("name", None)
                if local_name == name:
                    data[n] = local_library
                    found_canonical_library = True
            if not found_canonical_library:
                data.append(local_library)

    if list_libraries:
        log_libraries(data)
        return 0

    sdata = []
    if os.path.exists(state_filename):
        sdata = read_json_data(state_filename)

    # create source directory
    if not os.path.isdir(SRC_DIR):
        Logger.instance().info(f"[LOG] creating directory {SRC_DIR}")
        os.mkdir(SRC_DIR)

    # create archive files directory
    if not os.path.isdir(ARCHIVE_DIR):
        Logger.instance().info(f"[LOG] creating directory {ARCHIVE_DIR}")
        os.mkdir(ARCHIVE_DIR)

    failed_libraries = []

    for library in data:
        name = library.get("name", None)
        source = library.get("source", None)

        # get the src folder name
        src = source.get("src", "src")
        # get cmake arguments
        cmake_args = source.get("cmake_args", "")
        # get header_only options
        is_header_only = source.get("header_only", False)

        # get deps
        deps = source.get("deps", None)
        if not deps is None:
            libs = deps.get("libs", None)
            if not libs is None:
                for lib in libs:
                    deps_libs.append(lib)

            lib_paths = deps.get("paths", None)
            if not lib_paths is None:
                for lib_path in lib_paths:
                    deps_paths.append(lib_path)

        if (skip_libs) and (name in skip_libs):
            continue

        if (opt_names) and (not name in opt_names):
            continue

        lib_dir = os.path.join(SRC_DIR, name)
        lib_dir = lib_dir.replace(os.path.sep, "/")

        Logger.instance().info(f"[LOG] ********** LIBRARY {name} **********")
        Logger.instance().info(f"[LOG] lib_dir = ({lib_dir})")

        # compare against cached state
        cached_state_ok = False
        if not opt_clean:
            for slibrary in sdata:
                sname = slibrary.get("name", None)
                if (
                    sname is not None
                    and sname == name
                    and slibrary == library
                    and os.path.exists(lib_dir)
                ):
                    cached_state_ok = True
                    break

        if cached_state_ok:
            Logger.instance().info(
                f"[LOG] cached state for {name} equals expected state; skipping library"
            )
            continue
        else:
            # remove cached state for library
            sdata[:] = [
                s
                for s in sdata
                if not (
                    lambda s, name: s.get("name", None) is not None
                    and s["name"] == name
                )(s, name)
            ]

        # create library directory, if necessary
        if opt_clean:
            Logger.instance().info("[LOG] cleaning directory for {name}")
            if os.path.exists(lib_dir):
                shutil.rmtree(lib_dir)
        if not os.path.exists(lib_dir):
            os.makedirs(lib_dir)

        try:
            # download source
            if source is not None:
                if "type" not in source:
                    Logger.instance().info(
                        f"[ERROR] invalid schema for {name}: 'source' object must have a 'type'"
                    )
                    return -1
                if "url" not in source:
                    Logger.instance().info(
                        f"[ERROR] invalid schema for {name}: 'source' object must have a 'url'"
                    )
                    return -1
                src_type = source["type"]
                src_url = source["url"]

                if src_type == "sourcefile":
                    sha1 = source.get("sha1", None)
                    user_agent = source.get("user-agent", None)
                    try:
                        if force_fallback:
                            raise RuntimeError
                        download_file(
                            src_url,
                            ARCHIVE_DIR,
                            name,
                            sha1,
                            force_download=opt_clean_archives,
                            user_agent=user_agent,
                        )
                        filename_rel = os.path.basename(src_url)
                        shutil.copyfile(
                            os.path.join(ARCHIVE_DIR, filename_rel),
                            os.path.join(lib_dir, filename_rel),
                        )
                    except:
                        if FALLBACK_URL:
                            if not force_fallback:
                                Logger.instance().info(
                                    f"[WARNING] downloading of file {src_url} failed; trying fallback"
                                )

                            p = urlparse(src_url)
                            filename_rel = os.path.split(p.path)[
                                1
                            ]  # get original filename
                            p = urlparse(FALLBACK_URL)
                            fallback_src_url = urlunparse(
                                [
                                    p[0],
                                    p[1],
                                    p[2] + "/" + ARCHIVE_DIR_BASE + "/" + filename_rel,
                                    p[3],
                                    p[4],
                                    p[5],
                                ]
                            )
                            download_file(
                                fallback_src_url,
                                ARCHIVE_DIR,
                                name,
                                sha1,
                                force_download=True,
                            )
                            shutil.copyfile(
                                os.path.join(ARCHIVE_DIR, filename_rel),
                                os.path.join(lib_dir, filename_rel),
                            )
                        else:
                            shutil.rmtree(lib_dir)
                            raise
                elif src_type == "archive":
                    sha1 = source.get("sha1", None)
                    user_agent = source.get("user-agent", None)
                    try:
                        if force_fallback:
                            raise RuntimeError
                        download_and_extract_file(
                            src_url,
                            ARCHIVE_DIR,
                            name,
                            sha1,
                            force_download=opt_clean_archives,
                            user_agent=user_agent,
                        )
                    except:
                        if FALLBACK_URL:
                            if not force_fallback:
                                Logger.instance().info(
                                    f"[WARNING] downloading of file {src_url} failed; trying fallback"
                                )

                            p = urlparse(src_url)
                            filename_rel = os.path.split(p.path)[
                                1
                            ]  # get original filename
                            p = urlparse(FALLBACK_URL)
                            fallback_src_url = urlunparse(
                                [
                                    p[0],
                                    p[1],
                                    p[2] + "/" + ARCHIVE_DIR_BASE + "/" + filename_rel,
                                    p[3],
                                    p[4],
                                    p[5],
                                ]
                            )
                            download_and_extract_file(
                                fallback_src_url,
                                ARCHIVE_DIR,
                                name,
                                sha1,
                                force_download=True,
                            )
                        else:
                            raise
                else:
                    revision = source.get("revision", None)

                    archive_name = (
                        name + ".tar.gz"
                    )  # for reading or writing of snapshot archives
                    if revision is not None:
                        archive_name = name + "_" + revision + ".tar.gz"

                    try:
                        if force_fallback:
                            raise RuntimeError
                        clone_repository(src_type, src_url, name, revision)

                        # build library
                        if is_header_only:
                            generate_include_header_only(lib_dir, src)
                        else:
                            generate_lib_by_cmake(lib_dir, src, cmake_args)

                        if create_repo_snapshots:
                            Logger.instance().info(
                                f"[LOG] creating snapshot of library repository {name}"
                            )
                            repo_dir = os.path.join(SRC_DIR, name)
                            archive_filename = os.path.join(SNAPSHOT_DIR, archive_name)

                            Logger.instance().info(
                                "[LOG] snapshot will be saved as {archive_filename}"
                            )
                            create_archive_from_directory(
                                repo_dir, archive_filename, revision is None
                            )
                    except:
                        if FALLBACK_URL:
                            if not force_fallback:
                                Logger.instance().info(
                                    f"[WARNING] cloning of repository {src_url} failed; trying fallback"
                                )

                            # copy archived snapshot from fallback location
                            p = urlparse(FALLBACK_URL)
                            fallback_src_url = urlunparse(
                                [
                                    p[0],
                                    p[1],
                                    p[2] + "/" + SNAPSHOT_DIR_BASE + "/" + archive_name,
                                    p[3],
                                    p[4],
                                    p[5],
                                ]
                            )
                            Logger.instance().info(
                                f"[LOG] looking for snapshot {fallback_src_url} of library repository {name}"
                            )

                            # create snapshots files directory
                            download_and_extract_file(
                                fallback_src_url,
                                SNAPSHOT_DIR,
                                name,
                                force_download=True,
                            )

                            # reset repository state to particular revision (only using local operations inside the function)
                            clone_repository(src_type, src_url, name, revision, True)

                            # build library
                            if is_header_only:
                                generate_include_header_only(lib_dir, src)
                            else:
                                generate_lib_by_cmake(lib_dir, src, cmake_args)
                        else:
                            raise

            else:
                # set up clean directory for potential patch application
                shutil.rmtree(lib_dir)
                os.mkdir(lib_dir)

            # add to cached state
            sdata.append(library)

            # write out cached state
            write_json_data(sdata, state_filename)

        except urllib.error.URLError as e:
            Logger.instance().info(
                "[ERROR] failure to bootstrap library {name} (urllib.error.URLError: reason {str(e.reason)})"
            )
            if break_on_first_error:
                exit(-1)
            traceback.print_exc()
            failed_libraries.append(name)

        except:
            Logger.instance().info(
                "[ERROR] failure to bootstrap library {name} (reason: {str(sys.exc_info()[0])})"
            )
            if break_on_first_error:
                exit(-1)
            traceback.print_exc()
            failed_libraries.append(name)

    if failed_libraries:
        Logger.instance().info(f"[LOG] ***************************************")
        Logger.instance().info(f"[LOG] FAILURE to bootstrap the following libraries:")
        for failed_library in failed_libraries:
            Logger.instance().info(f"[LOG] {failed_library}")
        Logger.instance().info("[LOG]***************************************")
        return -1

    # dump deps.json
    if len(deps_libs) > 0:
        deps_libs = set(deps_libs)
        deps_paths = set(deps_paths)

        deps_data = {}
        deps_data["libs"] = list(deps_libs)
        deps_data["paths"] = list(deps_paths)

        write_json_data(deps_data, os.path.join(SRC_DIR, "deps.json"))

    Logger.instance().info("[LOG] Finished")
