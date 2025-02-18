# Copyright (C) 2024, Raffaello Bonghi <raffaello@rnext.it>
# All rights reserved
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING,
# BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import copy
import yaml
import pexpect
import getpass
import requests
import logging
import nanosaur.variables as nsv
from nanosaur.prompt_colors import TerminalFormatter

# Set up the logger
logger = logging.getLogger(__name__)

DEFAULT_ROBOT_CONFIG = {
    'name': 'nanosaur',
    'domain_id': 0,
    'simulation': False,
    'camera_type': '',
    'lidar_type': '',
    'engines': [],
}

CAMERA_CHOICES = ['', 'realsense', 'zed']
LIDAR_CHOICES = ['', 'LD06', 'rplidar']
ENGINES_CHOICES = ['vslam', 'nvblox', 'apriltag']


NANOSAUR_CONFIG_FILE_NAME = 'nanosaur.yaml'
NANOSAUR_HOME_NAME = 'nanosaur'
NANOSAUR_WEBSITE_URL = 'https://nanosaur.ai'
NANOSAUR_SPONSOR_URL = 'https://github.com/sponsors/rbonghi'
NANOSAUR_DISCORD_URL = 'https://discord.gg/rCHgeUpUj9'
NANOSAUR_GITHUB_ORG_URL = 'https://github.com/rnanosaur'
NANOSAUR_INSTAGRAM_URL = 'robo.panther'
NANOSAUR_MAIN_GITHUB_URL = 'https://github.com/rnanosaur/nanosaur.git'

NANOSAUR_DOCKER_USER = 'nanosaur'


def simulation_build_options(params, args=None):
    # Retrieve simulation data from parameters
    simulation_data = params.get('simulation', {})
    # Define options with default values
    options = {
        # 'tool': simulation_data.get('tool', ''),
        'headless': str(simulation_data.get('headless', False)).lower(),
        'isaac_sim_path': simulation_data.get('isaac_sim_path', ''),
        'world': simulation_data.get('world', '')
    }
    # Build the command string from options
    command = ' '.join(f"{key}:={value}" for key, value in options.items() if value)
    # Append additional arguments if provided
    if args:
        command = f"{command} {' '.join(args)}"
    return command


class Robot:

    @classmethod
    def load(cls, params):
        return cls(params['robot']) if 'robot' in params and params['robot'] else cls()

    def __init__(self, robot_config=None, name=None):
        if robot_config is None:
            robot_config = copy.deepcopy(DEFAULT_ROBOT_CONFIG)
        if name is not None:
            robot_config['name'] = name
        # Load the robot configuration
        for key, value in robot_config.items():
            setattr(self, key, value)

    def __repr__(self):
        attributes = ', '.join(
            f"{key}={value}" for key, value in self.__dict__.items()
            if key not in ['name', 'domain_id', 'simulation'] and value
        )
        sim_prefix = "(sim) " if self.simulation else ""
        base_repr = f"{sim_prefix}{self.name}[DID={self.domain_id}]"
        return f"{base_repr}({attributes})" if attributes else base_repr

    def to_dict(self) -> dict:
        return self.__dict__

    def config_to_ros(self) -> str:
        ros_params = []
        for key, value in self.__dict__.items():
            if key == 'domain_id' or not value:
                continue
            param_name = {
                'name': 'robot_name',
                'simulation': 'use_sim_time'
            }.get(key, key)
            if isinstance(value, list):
                value = f'"[{", ".join(value)}]"'
            ros_params.append(f"{param_name}:={value}")
        return ' '.join(ros_params)

    def verbose(self):
        """Print the robot configuration."""
        if self.simulation:
            print(TerminalFormatter.color_text("Robot: (simulated)", bold=True, color='magenta'))
        else:
            print(TerminalFormatter.color_text("Robot:", bold=True))
        print(f"  {TerminalFormatter.color_text('Name:', bold=True)} {self.name}")
        print(f"  {TerminalFormatter.color_text('Domain ID:', bold=True)} {self.domain_id}")
        print(f"  {TerminalFormatter.color_text('Camera:', bold=True)} {self.camera_type or 'not set'}")
        print(f"  {TerminalFormatter.color_text('Lidar:', bold=True)} {self.lidar_type or 'not set'}")
        print(f"  {TerminalFormatter.color_text('Engines:', bold=True)} {', '.join(self.engines) if self.engines else 'not set'}")
        # Print other attributes
        if other_attributes := {
            key: value
            for key, value in self.__dict__.items()
            if key not in ['name', 'simulation', 'domain_id', 'camera_type', 'lidar_type', 'engines']
        }:
            print(f"  {TerminalFormatter.color_text('Other attributes:', bold=True)}")
            for key, value in other_attributes.items():
                print(f"    {TerminalFormatter.color_text(f'{key}:', bold=True)} {value}")


class RobotList:

    @classmethod
    def get_idx_by_name(cls, params, robot_name) -> int:
        return cls.load(params)._get_idx_by_name(robot_name)

    @classmethod
    def add_robot(cls, params, robot, save=True) -> bool:
        robot_list = cls.load(params)
        if robot_list._add_robot(robot):
            params.set('robots', robot_list.to_dict(), save=save)
            params.set('robot_idx', len(robot_list.to_list()) - 1, save=save)
            return True
        return False

    @classmethod
    def remove_robot(cls, params, robot_idx=None):
        robot_list = cls.load(params)
        idx = robot_idx if robot_idx is not None else params.get('robot_idx', 0)
        if idx == 0:
            if 'robots' in params:
                del params['robots']
            if 'robot_idx' in params:
                del params['robot_idx']
        else:
            robot_list._remove_robot(idx)
            params['robots'] = robot_list.to_dict()
            if 'robot_idx' in params and params['robot_idx'] > 0:
                params['robot_idx'] -= 1

    @classmethod
    def update_robot(cls, params, robot) -> bool:
        robot_list = cls.load(params)
        idx = params.get('robot_idx', 0)
        if robot_list._update_robot(robot, idx):
            params['robots'] = robot_list.to_dict()
            return True
        return False

    @classmethod
    def current_robot(cls, params, idx=None) -> Robot:
        if idx is None:
            idx = params.get('robot_idx', 0)
        return cls.load(params).get_robot(idx)

    @classmethod
    def load(cls, params):
        return cls() if 'robots' not in params else cls(params['robots'])

    def __init__(self, robots=None):
        self.robots = [] if robots is None else [Robot(robot) for robot in robots]

    def _add_robot(self, robot) -> bool:
        def is_robot(robot):
            for r in self.robots:
                if r.name == robot.name:
                    return False
            return True

        if is_robot(robot):
            self.robots.append(robot)
            return True
        return False

    def _remove_robot(self, idx) -> bool:
        if idx < len(self.robots):
            del self.robots[idx]
            return True
        return False

    def _get_idx_by_name(self, name) -> int:
        return next((i for i, robot in enumerate(self.robots) if robot.name == name), None)

    def get_robot(self, idx) -> Robot:
        return self.robots[idx]

    def _get_robot_by_name(self, name) -> Robot:
        return next((robot for robot in self.robots if robot.name == name), None)

    def _update_robot(self, robot, idx) -> bool:
        if idx < len(self.robots):
            self.robots[idx] = robot
            return True
        return False

    def __repr__(self):
        return f"RobotList({self.robots})"

    def to_dict(self) -> list:
        return [robot.to_dict() for robot in self.robots]

    def to_list(self) -> list:
        return self.robots

    def print_all_robots(self, robot_idx=None):
        if robot_idx is not None:
            print(TerminalFormatter.color_text(f"All robots: (selected: {robot_idx})", bold=True))
        else:
            print(TerminalFormatter.color_text("All robots:", bold=True))
        for idx, robot in enumerate(self.robots):
            if idx == robot_idx:
                print(f"  {TerminalFormatter.color_text(f'Robot {idx}:', bold=True)} {TerminalFormatter.color_text(robot, color='green')}")
            else:
                print(f"  {TerminalFormatter.color_text(f'Robot {idx}:', bold=True)} {robot}")


class Params:

    @classmethod
    def load(cls, default_params):
        params_file = Params.get_params_file()
        # Load parameters from YAML file if it exists
        if os.path.exists(params_file):
            with open(params_file, 'r') as file:
                params_dict = yaml.safe_load(file)
        else:
            params_dict = default_params

        return cls(params_dict)

    def __init__(self, params_dict):
        self._params_dict = params_dict
        self._default_params = copy.deepcopy(params_dict)
        for key, value in params_dict.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._params_dict[key]

    def __setitem__(self, key, value):
        self._params_dict[key] = value
        setattr(self, key, value)
        # save the new value in the file
        self.save()

    def __delitem__(self, key):
        del self._params_dict[key]
        delattr(self, key)
        # save the new value in the file
        self.save()

    def __contains__(self, key):
        return key in self._params_dict

    def __repr__(self):
        return str(self._params_dict)

    def save(self):
        params_file = Params.get_params_file()
        # Save the parameters to the file if they are different from the default
        if params_file and self._params_dict != self._default_params:
            # Get the current nanosaur's home directory
            create_nanosaur_home()
            # Save the parameters to the file
            logger.debug(TerminalFormatter.color_text(f"Saving parameters to {params_file}", color='yellow'))
            with open(params_file, 'w') as file:
                yaml.dump(self._params_dict, file)

    @staticmethod
    def get_params_file() -> str:
        nanosaur_config_file_name = os.getenv('NANOSAUR_CONFIG_FILE', NANOSAUR_CONFIG_FILE_NAME)
        return os.path.join(get_nanosaur_home(), nanosaur_config_file_name)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def set(self, key, value, save=True):
        self._params_dict[key] = value
        setattr(self, key, value)
        # save the new value in the file
        if save:
            self.save()
        return value

    def items(self):
        return self._params_dict.items()


def is_env_file():
    nanosaur_home_path = get_nanosaur_home()
    env_path = os.path.join(nanosaur_home_path, '.env')
    return os.path.exists(env_path)


def build_env_file(params):
    nanosaur_home_path = get_nanosaur_home()
    # Get current robot running
    robot = RobotList.current_robot(params)
    uid = os.getuid()
    gid = os.getgid()
    env_path = os.path.join(nanosaur_home_path, f'{robot.name}.env')
    # Create a .env file and save UID and GID
    with open(env_path, 'w') as env_file:
        env_file.write(f"USER_UID={uid}\n")
        env_file.write(f"USER_GID={gid}\n")
        # Robot home folder
        env_file.write(f"ROBOT_HOME={nanosaur_home_path}\n")
        # Pass robot name
        env_file.write(f"ROBOT_NAME={robot.name}\n")
        # Pass robot simulation type
        core_tag = "simulation" if robot.simulation else "robot"
        env_file.write(f"CORE_TAG={core_tag}\n")
        # Pass robot perception type
        if robot.simulation:
            perception_tag = "simulation"
        elif robot.camera_type == 'realsense':
            perception_tag = "realsense"
        elif robot.camera_type == 'zed':
            perception_tag = "zed"
        else:
            perception_tag = "none"
        env_file.write(f"PERCEPTION_TAG={perception_tag}\n")
        # Load all commands to pass to the simulation
        if 'simulation' in params:
            simulation_commands = simulation_build_options(params)
            env_file.write(f"SIMULATION_COMMANDS={simulation_commands}\n")
        # Pass the nanosaur version
        nanosaur_version = params['nanosaur_version']
        if nsv.NANOSAUR_CURRENT_DISTRO != nanosaur_version:
            if '-' in nanosaur_version:
                nanosaur_version = nanosaur_version.split('-')[0]
            env_file.write(f"NANOSAUR_VERSION=-{nsv.NANOSAUR_CURRENT_DISTRO}\n")

        # Pass robot ros commands
        ros_args = robot.config_to_ros()
        if 'simulation' in params:
            simulation_data = params['simulation']
            ros_args += f" simulation_tool:={simulation_data['tool']}"
        env_file.write(f"COMMANDS={ros_args}\n")


def package_info(params: Params, verbose: bool):
    # Print version information
    sponsor_url = TerminalFormatter.clickable_link(NANOSAUR_SPONSOR_URL)
    print(f"{TerminalFormatter.color_text(' 💖 Sponsor:', bold=True)} {sponsor_url}")
    nanosaur_website = TerminalFormatter.clickable_link(NANOSAUR_WEBSITE_URL)
    print(f"{TerminalFormatter.color_text(' 🦕 Nanosaur website:', bold=True)} {nanosaur_website}")
    nanosaur_discord = TerminalFormatter.clickable_link(NANOSAUR_DISCORD_URL)
    print(f"{TerminalFormatter.color_text(' 🎮 Nanosaur Discord:', bold=True)} {nanosaur_discord}")
    nanosaur_instagram = TerminalFormatter.clickable_link(f"https://www.instagram.com/{NANOSAUR_INSTAGRAM_URL}")
    print(f"{TerminalFormatter.color_text(f' 📸 Follow {NANOSAUR_INSTAGRAM_URL}:', bold=True)} {nanosaur_instagram}")
    nanosaur_home_folder = TerminalFormatter.clickable_link(get_nanosaur_home())
    print(f"{TerminalFormatter.color_text(' 📂 Nanosaur home:', bold=True)} {nanosaur_home_folder}")
    # Print verbose information

    def print_verbose_info(params):
        nanosaur_github_url = TerminalFormatter.clickable_link(NANOSAUR_GITHUB_ORG_URL)
        print(f"{TerminalFormatter.color_text(' 🐱 GitHub:', bold=True)} {nanosaur_github_url}")
        nanosaur_docker_user = get_nanosaur_docker_user(params)
        nanosaur_docker_home = TerminalFormatter.clickable_link(f"https://hub.docker.com/u/{nanosaur_docker_user}")
        print(f"{TerminalFormatter.color_text(' 🐳 Docker Hub:', bold=True)} {nanosaur_docker_home}")
        config_file_path = TerminalFormatter.clickable_link(Params.get_params_file())
        print(f"{TerminalFormatter.color_text('Nanosaur config file:', bold=True)} {config_file_path}")
    if verbose:
        print_verbose_info(params)


def get_nanosaur_docker_user(params: Params) -> str:
    return params.get('nanosaur_docker_user', NANOSAUR_DOCKER_USER)


def get_nanosaur_raw_github_url(params: Params, nanosaur_branch) -> str:
    nanosaur_github_url = params.get('nanosaur_github', NANOSAUR_MAIN_GITHUB_URL)
    # Replace 'github.com' with 'raw.githubusercontent.com' in the URL
    nanosaur_github_url = nanosaur_github_url.replace('www.github.com', 'raw.githubusercontent.com')
    nanosaur_github_url = nanosaur_github_url.replace('github.com', 'raw.githubusercontent.com')
    # Remove '.git' suffix if present
    if nanosaur_github_url.endswith('.git'):
        nanosaur_github_url = nanosaur_github_url[:-4]
    # Append the branch name to the URL
    return f"{nanosaur_github_url}/{nanosaur_branch}"


def create_nanosaur_home() -> str:
    # Get the current nanosaur's home directory
    nanosaur_home_path = get_nanosaur_home()
    # Check if folder exists, if not, create it
    if not os.path.exists(nanosaur_home_path):
        os.makedirs(nanosaur_home_path)
        logger.debug(TerminalFormatter.color_text(f"Folder '{nanosaur_home_path}' created.", color='green'))
    return nanosaur_home_path


def get_nanosaur_home() -> str:
    """ Get the nanosaur home directory. """
    # Check if the environment variable is set
    if 'NANOSAUR_HOME' in os.environ:
        return os.environ['NANOSAUR_HOME']
    # Get the current nanosaur's home directory
    return os.path.join(os.path.expanduser("~"), NANOSAUR_HOME_NAME)


def download_file(url, folder_path, file_name, force=False) -> str:
    # Create the full file path
    file_path = os.path.join(folder_path, file_name)

    # Check if the file already exists
    if not force and os.path.exists(file_path):
        logger.debug(TerminalFormatter.color_text(f"File '{file_name}' already exists in '{folder_path}'. Skip download", color='yellow'))
        return file_path  # Cancel download

    # Send a request to download the file
    response = requests.get(url)

    if response.status_code == 200:
        # Save the file in the workspace folder
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, 'wb') as file:
            file.write(response.content)
        logger.debug(TerminalFormatter.color_text(f"File '{file_name}' downloaded successfully to '{folder_path}'.", color='green'))
        return file_path
    else:
        print(TerminalFormatter.color_text(f"Failed to download file. Status code: {response.status_code}", color='red'))
        return None


def require_sudo(func):
    def wrapper(*args, **kwargs):
        if os.geteuid() != 0:
            print(
                TerminalFormatter.color_text(
                    "This script must be run as root. Please use 'sudo'.",
                    color='red'))
            return False
        return func(*args, **kwargs)
    return wrapper


def require_sudo_password(func):
    def wrapper(*args, **kwargs):
        child = None
        try:
            # Get password
            print(TerminalFormatter.color_text("This function require user password to be executed.", color='yellow'))
            # Get the username
            username = os.getlogin()
            # Get the password
            password = getpass.getpass(prompt=f'{TerminalFormatter.color_text("[sudo]", bold=True)} password for {username}: ')
            # Test if the sudo password is valid
            child = pexpect.spawn("sudo -v")
            child.expect("password for")
            child.sendline(password)
            index = child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=10)
            if index != 0:  # Password not accepted
                print("Error: Incorrect sudo password. Please try again.")
                return False
            # Execute function with password
            return func(*args, password=password, **kwargs)
        except Exception as e:
            print(f"Validation error: {e}")
            return False
        except KeyboardInterrupt:
            print(TerminalFormatter.color_text("Exiting...", color='yellow'))
            return False
        finally:
            if child is not None:
                child.close()
    return wrapper


def conditional_sudo_password(func):
    def wrapper(platform, params, args):
        if args.force:
            return require_sudo_password(func)(platform, params, args)
        else:
            return func(platform, params, args)
    return wrapper
# EOF
