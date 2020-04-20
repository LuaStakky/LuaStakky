import os
import requests
import sys
import shutil
from pathlib import Path
from abc import ABC, abstractmethod
from gitignore_parser import parse_gitignore


class StakkyFile(ABC):
    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        return open(self.get_global_alias(), mode=mode, buffering=buffering, encoding=encoding, errors=errors,
                    newline=newline, closefd=closefd, opener=opener)

    # return path from build dir
    @abstractmethod
    def get_build_alias(self):
        pass

    # return path from work dir
    @abstractmethod
    def get_project_alias(self):
        pass

    # return path that can be open to read from python
    @abstractmethod
    def get_global_alias(self):
        pass


# Temp build file (in .build folder)
class StakkyBuildFile(StakkyFile):
    def __init__(self, path, fs_profile_controller):
        self._path = path
        self._fs_profile_controller = fs_profile_controller

    def get_build_alias(self):
        return self._path

    def get_project_alias(self):
        return os.path.join(self._fs_profile_controller.build_dir_local_path, self._path)

    def get_global_alias(self):
        return os.path.join(self._fs_profile_controller.build_dir, self._path)


# Project file
class StakkyProjectFile(StakkyFile):
    def __init__(self, path, fs_profile_controller):
        self._path = path
        self._fs_profile_controller = fs_profile_controller

    def get_build_alias(self):
        return ('..' + os.path.sep) * self._fs_profile_controller.build_dir_nesting + self._path

    def get_project_alias(self):
        return self._path

    def get_global_alias(self):
        return os.path.join(self._fs_profile_controller.work_dir, self._path)


class FsProfileController:
    _branch = 'master'
    build_files = set()

    def __init__(self, profile_name, fs_controller=None, build_dir=os.path.join('.build', 'default')):
        self.profile_name = profile_name
        self._fs_controller = fs_controller
        self.work_dir = fs_controller.work_dir

        # Check build folder
        self.build_dir_local_path = build_dir
        self.build_dir = os.path.join(self.work_dir, build_dir)
        self.build_dir_nesting = build_dir.count('/', 1, -1) + build_dir.count('\\', 1, -1) + 1

        # clear last build
        if os.path.isdir(self.build_dir):
            shutil.rmtree(self.build_dir)
        os.mkdir(self.build_dir)

        fs_controller.try_add_to_gitignore(build_dir + os.path.sep)

    def mk_build_subdir(self, subdir):
        subdir_name = subdir
        i = 0
        while subdir_name in self.build_files:
            i = i + 1
            subdir_name = subdir + "." + str(i)
        if not os.path.exists(os.path.dirname(os.path.join(self.build_dir, subdir_name))):
            os.makedirs(os.path.dirname(os.path.join(self.build_dir, subdir_name)))

        if not os.path.isdir(os.path.join(self.build_dir, subdir_name)):
            os.mkdir(os.path.join(self.build_dir, subdir_name))
        return StakkyBuildFile(subdir_name, self)

    def mk_build_file(self, file):
        file_name = file
        i = 0
        while file_name in self.build_files:
            i = i + 1
            file_name = file + "." + str(i)
        if not os.path.exists(os.path.dirname(os.path.join(self.build_dir, file_name))):
            os.makedirs(os.path.dirname(os.path.join(self.build_dir, file_name)))
        Path(os.path.join(self.build_dir, file_name)).touch()
        return file_name

    def download_file(self, url, path):
        file = StakkyBuildFile(self.mk_build_file(path), self)
        with file.open("wb") as f:
            print('Downloading ' + url)
            response = requests.get(url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                f.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    done = int(50 * min(dl / total_length,1))
                    sys.stdout.write('\r[' + '=' * done + ' ' * (50 - done) + ']')
                    sys.stdout.flush()
                sys.stdout.write('\n')
        return file

    def get_file_from_repo(self, repo_path, path):
        file = StakkyBuildFile(self.mk_build_file(path), self)
        self.download_file('https://raw.githubusercontent.com/LuaStakky/LuaStakky-lib-repo/' + self._branch + '/' + repo_path, file.get_global_alias())
        return file


class FsController:
    loaded_profiles = {}

    def __init__(self, work_dir='.'):
        self.work_dir = work_dir
        if not os.path.exists(os.path.join(work_dir, '.build')):
            os.makedirs(os.path.join(work_dir, '.build'))

        # IgnoreInit
        self._gitignore_path = os.path.join(work_dir, ".gitignore")
        self._reload_gitignore()

    def _reload_gitignore(self):
        self._gitignore = parse_gitignore(self._gitignore_path) if os.path.isfile(self._gitignore_path) else lambda \
                x: False

    def try_add_to_gitignore(self, path):
        if self._gitignore(os.path.join(self.work_dir, path)):
            # Ignore Update
            with open(self._gitignore_path, 'a') as gitignore:
                gitignore.writelines([path])
            self._reload_gitignore()

    def get_profile_controller(self, name):
        if name not in self.loaded_profiles:
            self.loaded_profiles[name] = FsProfileController(name, fs_controller=self,
                                                             build_dir=os.path.join('.build', name))
        return self.loaded_profiles[name]
