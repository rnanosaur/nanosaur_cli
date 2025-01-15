# PYTHON_ARGCOMPLETE_OK
# Copyright (C) 2025, Raffaello Bonghi <raffaello@rnext.it>
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
import argparse
import argcomplete
import sys
from jtop import jtop, JtopException

from nanosaur import __version__
from nanosaur.utilities import Params
from nanosaur import workspace
from nanosaur import simulation
from nanosaur import robot
from nanosaur.workspace import get_workspace_path
from nanosaur.prompt_colors import TerminalFormatter

NANOSAUR_CONFIG_FILE = 'nanosaur.yaml'

# Define default parameters
DEFAULT_PARAMS = {
    'nanosaur_workspace_name': 'nanosaur_ws',
    'nanosaur_branch': 'nanosaur2',
    'robot_name': 'nanosaur',
    'domain_id': 0,
}


def info(platform, params: Params, args):
    """Print version information."""
    print(f"Nanosaur package version {__version__}")
    # Print configuration parameters
    print("\nConfiguration:")
    for key, value in params.items():
        if value:  # Only print if value is not empty
            print(f"  {key}: {value}")
    # Print device information
    print("\nPlatform Information:")
    for key, value in platform.items():
        print(f"  {key}: {value}")


def install(platform, params: Params, args):
    device_type = "robot" if platform['Machine'] == 'jetson' else "desktop"
    print(TerminalFormatter.color_text(f"Installing Nanosaur for {device_type}...", color='green'))
    if device_type == 'desktop':
        simulation.simulation_install(platform, params, args)
    elif device_type == 'robot':
        print(TerminalFormatter.color_text("Robot installation not supported yet.", color='red'))


def parser_workspace_menu(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser_workspace = subparsers.add_parser(
        'workspace', aliases=["ws"], help="Manage the Nanosaur workspace")
    workspace_subparsers = parser_workspace.add_subparsers(
        dest='workspace_type', help="Workspace types")
    # Add workspace clean subcommand
    parser_workspace_clean = workspace_subparsers.add_parser(
        'clean', help="Clean the workspace")
    parser_workspace_clean.add_argument(
        '--force', action='store_true', help="Force the workspace clean")
    parser_workspace_clean.set_defaults(func=workspace.clean)
    # Add workspace update subcommand
    parser_workspace_update = workspace_subparsers.add_parser(
        'update', help="Update the workspace")
    parser_workspace_update.add_argument(
        '--force', action='store_true', help="Force the update")
    parser_workspace_update.set_defaults(func=workspace.update)
    return parser_workspace


def parser_simulation_menu(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser_simulation = subparsers.add_parser(
        'simulation', aliases=["sim"], help="Work with simulation tools")
    simulation_subparsers = parser_simulation.add_subparsers(
        dest='simulation_type', help="Simulation types")

    # Add simulation start subcommand
    parser_simulation_start = simulation_subparsers.add_parser(
        'start', help="Start the selected simulation")
    parser_simulation_start.set_defaults(func=simulation.simulation_start)

    # Add simulation set subcommand
    parser_simulation_set = simulation_subparsers.add_parser(
        'set', help="Select the simulator you want to use")
    parser_simulation_set.set_defaults(func=simulation.simulation_set)
    return parser_simulation


def main():
    # Load the parameters
    user_home_dir = os.path.expanduser("~")
    params = Params.load(DEFAULT_PARAMS, params_file=f'{user_home_dir}/{NANOSAUR_CONFIG_FILE}')

    # Extract device information with jtop
    try:
        with jtop() as device:
            if device.ok():
                platform = device.board['platform']
    except JtopException as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Determine the device type
    device_type = "robot" if platform['Machine'] == 'jetson' else "desktop"

    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="Nanosaur CLI - A command-line interface for the Nanosaur package.")

    # Define subcommands
    subparsers = parser.add_subparsers(dest='command', help="Available commands")

    # Subcommand: info
    parser_info = subparsers.add_parser('info', help="Show version information")
    parser_info.set_defaults(func=info)

    # Subcommand: install (hidden if workspace already exists)
    if get_workspace_path(params['nanosaur_workspace_name']) is None:
        parser_install = subparsers.add_parser('install', help="Install the Nanosaur workspace")
    else:
        parser_install = subparsers.add_parser('install')
    # Add simulation install subcommand
    parser_install.add_argument('--developer', action='store_true', help="Install developer workspace")
    parser_install.add_argument('--force', action='store_true', help="Force the update")
    parser_install.set_defaults(func=install)

    # Subcommand: workspace (with a sub-menu for workspace operations)
    if get_workspace_path(params['nanosaur_workspace_name']) is not None:
        # Add workspace subcommand
        parser_workspace = parser_workspace_menu(subparsers)

    # Subcommand: simulation (with a sub-menu for simulation types)
    if device_type == 'desktop' and get_workspace_path(params['nanosaur_workspace_name']) is not None:
        # Add simulation subcommand
        parser_simulation = parser_simulation_menu(subparsers)

    # Subcommand: robot (with a sub-menu for robot operations)
    parser_robot = subparsers.add_parser('robot', help="Manage the Nanosaur robot")
    robot_subparsers = parser_robot.add_subparsers(dest='robot_type', help="Robot operations")

    # Add robot drive subcommand
    parser_robot_drive = robot_subparsers.add_parser('drive', help="Drive the robot")
    parser_robot_drive.set_defaults(func=robot.control_keyboard)
    # Add robot start subcommand
    parser_robot_start = robot_subparsers.add_parser('start', help="Start the robot")
    parser_robot_start.set_defaults(func=robot.robot_start)

    # Add robot name subcommand
    parser_robot_name = robot_subparsers.add_parser('name', help="Set the robot name")
    parser_robot_name.add_argument('name', type=str, help="Name of the robot")
    parser_robot_name.set_defaults(func=robot.robot_set_name)
    # Add robot domain id subcommand
    parser_robot_domain_id = robot_subparsers.add_parser('domain_id', help="Set the robot domain ID")
    parser_robot_domain_id.add_argument('domain_id', type=int, help="Domain ID of the robot")
    parser_robot_domain_id.set_defaults(func=robot.robot_set_domain_id)

    # Enable tab completion
    argcomplete.autocomplete(parser)

    # Parse the arguments
    args = parser.parse_args()

    # Handle workspace subcommand without a workspace_type
    if args.command in ['workspace', 'ws'] and args.workspace_type is None:
        parser_workspace.print_help()
        sys.exit(1)

    # Handle install subcommand without an install_type
    if args.command in ['simulation', 'sim'] and args.simulation_type is None:
        parser_simulation.print_help()
        sys.exit(1)

    if args.command in ['robot'] and args.robot_type is None:
        parser_robot.print_help()
        sys.exit(1)

    # Execute the corresponding function based on the subcommand
    if hasattr(args, 'func'):
        args.func(platform, params, args)
    else:
        # If no command is provided, display a custom help message without the
        # list of commands
        parser.print_help()


if __name__ == "__main__":
    main()
# EOF
