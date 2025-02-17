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

import re
import os
import shutil
import inquirer
from inquirer.themes import GreenPassion
import argparse
import subprocess
import logging
import nanosaur.variables as nsv
from nanosaur import workspace
from nanosaur.docker import docker_simulator_start
from nanosaur.prompt_colors import TerminalFormatter
from nanosaur.utilities import Params, RobotList
from packaging.version import parse  # type: ignore
import operator

# Set up the logger
logger = logging.getLogger(__name__)


# Define a mapping of operators to functions
MAP_OPERATOR_VERSION = {
    '>=': operator.ge,
    '<=': operator.le,
    '>': operator.gt,
    '<': operator.lt,
    '==': operator.eq,
    '!=': operator.ne,
}

# Regex to separate operator and version
PATTERN_VERSION = re.compile(r'(>=|<=|>|<|==|!=)\s*([\d\.]+)')

# Dictionary of simulation tools and their commands
simulation_tools = {
    "isaac-sim": {
        "simulator": "ros2 launch isaac_sim_wrapper isaac_sim_server.launch.py",
        "robot": "ros2 launch nanosaur_isaac-sim nanosaur_bridge.launch.py"
    },
    "gazebo": {
        "simulator": "ros2 launch nanosaur_gazebo gazebo.launch.py",
        "robot": "ros2 launch nanosaur_gazebo nanosaur_bridge.launch.py"
    }
}

SIMULATION_WORLD_CHOICES = ['empty', 'lab', 'office', 'warehouse']


def parser_simulation_menu(subparsers: argparse._SubParsersAction, params: Params) -> argparse.ArgumentParser:
    # Get the simulation data from the parameters
    simulation_data = params.get('simulation', {})
    # Get the simulation tool from the parameters
    simulation_type = simulation_data.get('tool', "NOT SELECTED")
    # Add simulation subcommand
    parser_simulation = subparsers.add_parser(
        'simulation', aliases=["sim"], help=f"Work with simulation tools [{simulation_type}]")
    simulation_subparsers = parser_simulation.add_subparsers(
        dest='simulation_type', help="Simulation types")

    # Add simulation start subcommand
    parser_simulation_start = simulation_subparsers.add_parser(
        'start', help="Start the selected simulation")
    parser_simulation_start.add_argument(
        '--debug', action='store_true', help="Start the simulation in debug mode")
    parser_simulation_start.set_defaults(func=simulation_start)

    # Add simulation set subcommand
    parser_simulation_set = simulation_subparsers.add_parser(
        'set', help="Select the simulator you want to use")
    parser_simulation_set.set_defaults(func=simulation_set)

    # Add simulation world subcommand
    parser_simulation_world = simulation_subparsers.add_parser(
        'world', help="Set a world for the simulation")
    parser_simulation_world.add_argument('--new', type=str, help="Specify another world not listed")
    parser_simulation_world.set_defaults(func=simulation_set_world)

    # Add simulation headless subcommand
    parser_simulation_headless = simulation_subparsers.add_parser(
        'headless', help="Set the simulation in headless mode")
    parser_simulation_headless.set_defaults(func=simulation_set_headless)
    return parser_simulation


def find_all_isaac_sim():
    # Paths where Isaac Sim is usually installed
    base_paths = [
        os.path.expanduser("~/.local/share/ov/pkg"),
        os.path.expanduser("~")
    ]
    isaac_sim_folders = {}

    for base_path in base_paths:
        if os.path.exists(base_path):
            # Look for directories in the base path
            for folder in os.listdir(base_path):
                full_path = os.path.join(base_path, folder)
                if version := check_isaac_sim(full_path):
                    isaac_sim_folders[version] = full_path
    # Return a dictionary with the version as key and the full path as value, sorted by latest version
    return dict(sorted(isaac_sim_folders.items(), key=lambda item: item[0], reverse=True))


def check_isaac_sim(full_path):
    """
    Validate if the given path contains a valid Isaac Sim installation.

    :param full_path: The full path to the directory to validate.
    :type full_path: str
    :return: The version of Isaac Sim if valid, otherwise None.
    :rtype: str or None
    """
    version_file = os.path.join(full_path, "VERSION")
    isaac_sim_script = os.path.join(full_path, "isaac-sim.sh")
    python_script = os.path.join(full_path, "python.sh")
    if os.path.isfile(version_file) and os.path.isfile(isaac_sim_script) and os.path.isfile(python_script):
        with open(version_file, 'r') as vf:
            return vf.read().strip().split('-')[0]
    return None


def validate_isaac_sim(isaac_sim_path, required):
    # Extract conditions properly
    conditions = PATTERN_VERSION.findall(required)
    if version := check_isaac_sim(isaac_sim_path):
        return all(MAP_OPERATOR_VERSION[op](parse(version), parse(ver)) for op, ver in conditions)
    return False


def is_gazebo_installed(folder="/usr/share/gazebo"):
    """
    Check if Gazebo is installed by verifying the existence of the Gazebo binary
    or the installation folder.

    :param folder: Path to the folder where Gazebo is typically installed (default: /usr/share/gazebo).
    :return: True if Gazebo is installed, False otherwise.
    """
    if shutil.which("gazebo") or shutil.which("gz"):
        return True
    # Check if the default Gazebo folder exists
    return bool(os.path.exists(folder) and os.path.isdir(folder))


def is_simulation_tool_installed():
    """
    Check if either Gazebo or Isaac Sim is installed.

    :return: A dictionary indicating the installation status of Gazebo and Isaac Sim.
    """
    return bool(find_all_isaac_sim()) or is_gazebo_installed()


def simulation_info(platform, params: Params, verbose):
    """
    Print information about the installed simulation tools.
    """
    # Get the simulation data from the parameters
    simulation_data = params.get('simulation', {})

    def print_simulation_tool():
        isaac_sim_version = ""
        if 'isaac_sim_path' in simulation_data and simulation_data['tool'] == 'isaac-sim' and simulation_data['isaac_sim_path']:
            version_file = os.path.join(simulation_data['isaac_sim_path'], "VERSION")
            if os.path.isfile(version_file):
                with open(version_file, 'r') as vf:
                    isaac_sim_version = vf.read().strip().split('-')[0]  # Read the version from the VERSION file and cut after the first '-'
        text_message = f"{TerminalFormatter.color_text('   selected:', bold=True)} {simulation_data['tool']} {isaac_sim_version}"
        print(text_message)
        headless_md = simulation_data.get('headless', False)
        headless_string = TerminalFormatter.color_text('enabled', color='green') if headless_md else TerminalFormatter.color_text('disabled', color='red')
        print(f"{TerminalFormatter.color_text('   Headless mode:', bold=True)} {headless_string}")
        if headless_md and simulation_data['tool'] == 'isaac-sim':
            link_livestream = TerminalFormatter.clickable_link("https://docs.isaacsim.omniverse.nvidia.com/latest/installation/manual_livestream_clients.html")
            print(f"{TerminalFormatter.color_text('   Livestream:', bold=True)} {link_livestream}")

    # Check if any simulation tools are installed
    if not is_simulation_tool_installed():
        print(TerminalFormatter.color_text("No simulation tools installed", color='red'))
        return

    print(TerminalFormatter.color_text("Simulation:", bold=True))
    if 'tool' in simulation_data:
        print_simulation_tool()

    elif platform['Machine'] != 'aarch64':
        print(TerminalFormatter.color_text("   No simulation tool selected", color='red'))

    # Check if Isaac Sim is installed
    if verbose:
        if isaac_sim_list := find_all_isaac_sim():
            print(TerminalFormatter.color_text("   Isaac Sim installed:", bold=True))
            for version, path in isaac_sim_list.items():
                print(f"    - Isaac Sim {version}: {path}")
        # Check if Gazebo is installed
        if is_gazebo_installed():
            print(TerminalFormatter.color_text("   Gazebo is installed", bold=True))


def simulation_robot_start_debug(params, args):
    nanosaur_ws_path = workspace.get_workspace_path(params, 'ws_simulation_name')
    bash_file = os.path.join(nanosaur_ws_path, 'install', 'setup.bash')
    simulation_data = params.get('simulation', {})
    # Check if the install folder exists
    if not os.path.exists(bash_file):
        print(TerminalFormatter.color_text("Workspace not built. Build before to debug", color='red'))
        return False
    # Check which simulation tool is selected
    if 'tool' not in simulation_data:
        print(TerminalFormatter.color_text("No simulation tool selected. Please select a simulator first.", color='red'))
        return False
    # Check if the simulation tool is valid and get the command
    command = simulation_tools[simulation_data['tool']]['robot']
    # Load the robot configuration
    robot = RobotList.current_robot(params)
    print(TerminalFormatter.color_text(f"Starting {robot}", color='green'))

    exec_command = f"ROS_DOMAIN_ID={robot.domain_id} {command} {robot.config_to_ros()} {' '.join(args)}"
    # Print the command to be run
    print(exec_command)

    try:
        # Combine sourcing the bash file with running the command
        process = subprocess.Popen(
            f"source {bash_file} && {exec_command}",
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Stream output live
        for line in process.stdout:
            # Decode and print stdout line-by-line
            print(line.decode('utf-8'), end="")

        # Wait for the process to finish
        process.wait()

        # Stream any errors
        for line in process.stderr:
            print(TerminalFormatter.color_text(line.decode('utf-8'), color='red'), end="")  # Print stderr (errors) in red

        return process.returncode == 0
    except KeyboardInterrupt:
        return False
    except Exception as e:
        print(f"An error occurred while running the command: {e}")
        return False


def simulation_start_debug(simulation_ws_path, simulation_tool, headless, world, isaac_sim_path, args=None):
    """Install the simulation tools."""

    bash_file = f'{simulation_ws_path}/install/setup.bash'
    # Check if the install folder exists
    if not os.path.exists(bash_file):
        print(TerminalFormatter.color_text("Workspace not built. Build before to debug", color='red'))
        return False

    command = simulation_tools[simulation_tool]['simulator']
    command += f" headless:={str(headless).lower()}"
    # add isaac_sim_path if available
    if isaac_sim_path:
        command = f"{command} isaac_sim_path:={isaac_sim_path}"
    # add world if available
    if world:
        command = f"{command} world:={world}"
    # add additional arguments
    if args:
        command = f"{command} {' '.join(args)}"
    # Print the command to be run
    logger.debug(command)
    try:
        # Combine sourcing the bash file with running the command
        process = subprocess.Popen(
            f"source {bash_file} && {command}",
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Stream output live
        for line in process.stdout:
            # Decode and print stdout line-by-line
            print(line.decode('utf-8'), end="")

        # Wait for the process to finish
        process.wait()

        # Stream any errors
        for line in process.stderr:
            print(TerminalFormatter.color_text(line.decode('utf-8'), color='red'), end="")  # Print stderr (errors) in red

        return process.returncode == 0
    except KeyboardInterrupt:
        return False
    except Exception as e:
        print(f"An error occurred while running the command: {e}")
        return False


def simulation_start(platform, params: Params, args):
    # Get location starting function (host or docker)
    selected_location = workspace.get_starting_location(params)
    if selected_location is None:
        return False
    # Get the simulation data from the parameters
    simulation_data = params.get('simulation', {})
    # Check which simulation tool is selected
    if 'tool' not in simulation_data:
        print(TerminalFormatter.color_text("No simulation tool selected. Please run simulation set first.", color='red'))
        return False
    # Check if the simulation tool is valid
    if simulation_data['tool'] not in simulation_tools:
        print(TerminalFormatter.color_text(f"Unknown simulation tool: {simulation_data['tool']}", color='red'))
        return False
    # Check if Isaac Sim is selected but no version is set
    if simulation_data['tool'] == 'isaac-sim' and 'isaac_sim_path' not in simulation_data:
        print(TerminalFormatter.color_text("No Isaac Sim version selected. Please run simulation set first.", color='red'))
        return False
    # Check if the debug mode is enabled
    if selected_location == 'host':
        nanosaur_ws_path = workspace.get_workspace_path(params, 'ws_simulation_name')
        simulator_tool = simulation_data['tool']
        headless = simulation_data.get('headless', False)
        world = simulation_data.get('world', '')
        return simulation_start_debug(nanosaur_ws_path, simulator_tool, headless, world, simulation_data.get('isaac_sim_path', None))
    elif selected_location == 'docker':
        # Run from docker container
        return docker_simulator_start(platform, params, args)
    else:
        print(TerminalFormatter.color_text(f"Unknown debug mode: {selected_location}", color='red'))
        return False


def simulation_set(platform, params: Params, args):
    """Set the simulation tools."""
    # Get the current simulation tool
    simulation_data = params.get('simulation', {})
    current_tool = simulation_data.get('tool', None)
    # Capitalize the current tool name
    if current_tool:
        current_tool = current_tool.capitalize()
    # Check if Gazebo is installed
    if not is_gazebo_installed():
        simulation_tools.pop('gazebo', None)
    # Find all installed Isaac Sim versions
    isaac_sim_list = find_all_isaac_sim()
    # Get the version of Isaac Sim if it is already set
    current_version = None
    if 'isaac_sim_path' in simulation_data:
        current_version = simulation_data['isaac_sim_path'].split("isaac-sim-")[-1]  # Extract version after "isaac-sim-"
    # Check if any simulation tools are available
    if not simulation_tools:
        print(TerminalFormatter.color_text("No simulation tools available. Please install a simulator first.", color='red'))
        return False
    # Get the Isaac Sim version required for the selected Nanosaur version
    isaac_sim_required = nsv.NANOSAUR_DISTRO_MAP[params['nanosaur_version']]['isaac_sim']
    # Filter the list with only the valid Isaac Sim versions
    isaac_sim_list = {ver: path for ver, path in isaac_sim_list.items() if validate_isaac_sim(path, isaac_sim_required)}
    # Ask the user to select a simulation tool
    questions = [
        inquirer.List(
            'tool',
            message="Set the simulation tools",
            choices=[tool.capitalize() for tool in simulation_tools.keys()],
            default=current_tool
        ),
        inquirer.List(
            'isaac-sim',
            message="Select Isaac Sim version for run on host",
            choices=list(isaac_sim_list.keys()) + ["Custom Path"],
            default=current_version,
            ignore=lambda answers: answers['tool'] != 'Isaac-sim' or not isaac_sim_list
        ),
        inquirer.Path(
            'custom_isaac_sim_path',
            message="Enter the custom path for Isaac Sim",
            path_type=inquirer.Path.DIRECTORY,
            ignore=lambda answers: answers.get('isaac-sim') != 'Custom Path'
        )
    ]
    # Ask the user to select a simulation tool
    answers = inquirer.prompt(questions, theme=GreenPassion())
    if answers is None:
        return False
    # Save the selected simulation tool
    simulation_data['tool'] = answers['tool'].lower()
    if simulation_data['tool'] == 'isaac-sim' and answers['isaac-sim'] is not None:
        if answers['isaac-sim'] == "Custom Path":
            if version := check_isaac_sim(answers['custom_isaac_sim_path']):
                if validate_isaac_sim(answers['custom_isaac_sim_path'], isaac_sim_required):
                    print(TerminalFormatter.color_text(f"Selected Isaac Sim version: {version}", color='green'))
                else:
                    print(TerminalFormatter.color_text(f"Isaac Sim {version} not tested for this nanosaur version", color='yellow'))
                simulation_data['isaac_sim_path'] = answers['custom_isaac_sim_path']
            else:
                print(TerminalFormatter.color_text("Invalid Isaac Sim path", color='red'))
                return False
        else:
            print(TerminalFormatter.color_text(f"Selected Isaac Sim version: {answers['isaac-sim']}", color='green'))
            simulation_data['isaac_sim_path'] = isaac_sim_list[answers['isaac-sim']]

    else:
        print(TerminalFormatter.color_text(f"Selected {answers['tool']}", color='green'))
    # Store the new simulation data
    params['simulation'] = simulation_data
    return True


def simulation_set_headless(platform, params: Params, args):
    # Get the current simulation tool
    simulation_data = params.get('simulation', {})
    headless_mode = simulation_data.get('headless', False)
    # Ask the user if they want to run in headless mode
    question = [
        inquirer.List(
            'headless',
            message="Select if you want run the simulation in headless mode",
            choices=['Yes', 'No'],
            default='Yes' if headless_mode else 'No'
        )
    ]
    # Get the user's answer
    answer = inquirer.prompt(question, theme=GreenPassion())
    if answer is None:
        return False
    # Save the headless mode setting
    simulation_data['headless'] = (answer['headless'] == 'Yes')
    params['simulation'] = simulation_data
    print(TerminalFormatter.color_text(f"Headless mode set to: {answer['headless']}", color='green'))
    return True


def simulation_set_world(platform, params: Params, args):
    # Get the current simulation tool
    simulation_data = params.get('simulation', {})
    world = simulation_data.get('world', '')

    # Get the list of available worlds
    all_worlds = SIMULATION_WORLD_CHOICES.copy()
    # Add the current world to the list if it's not already included
    if world and world not in all_worlds:
        all_worlds.append(world)

    if args.new is not None:
        if args.new not in all_worlds:
            all_worlds.append(args.new)
            simulation_data['world'] = args.new
            params['simulation'] = simulation_data
            print(TerminalFormatter.color_text(f"World {args.new} added", color='green'))
        else:
            print(TerminalFormatter.color_text(f"World {args.new} already exists", color='red'))
            return False
        return True

    # Ask the user to select a world
    question = [
        inquirer.List(
            'world',
            message="Select the world for the simulation",
            choices=all_worlds,
            default=world
        )
    ]
    # Get the user's answer
    answer = inquirer.prompt(question, theme=GreenPassion())
    if answer is None:
        return False
    # Save the selected world
    simulation_data['world'] = answer['world']

    params['simulation'] = simulation_data
    # print(TerminalFormatter.color_text(f"Headless mode set to: {answer['headless']}", color='green'))
    return True
# EOF
