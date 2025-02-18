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

import inquirer
from inquirer.themes import GreenPassion
import argparse
import subprocess
import shlex
import logging
from nanosaur import workspace
from nanosaur import docker
from nanosaur.prompt_colors import TerminalFormatter
from nanosaur.utilities import Params, RobotList, Robot
from nanosaur.utilities import ENGINES_CHOICES, CAMERA_CHOICES, LIDAR_CHOICES

# Set up the logger
logger = logging.getLogger(__name__)


def add_robot_config_subcommands(platform, subparsers: argparse._SubParsersAction, params: Params) -> argparse.ArgumentParser:
    # Get the robot data
    robot_data = RobotList.current_robot(params)
    robot_name = TerminalFormatter.color_text(robot_data.name, color='green', bold=True)
    parser_robot_config = subparsers.add_parser('config', help=f"Configure the robot settings [{robot_name}]")
    config_subparsers = parser_robot_config.add_subparsers(dest='config_type', help="Configuration options")
    # Add robot name subcommand
    parser_robot_name = config_subparsers.add_parser('name', help=f"Set robot name [{robot_name}]")
    parser_robot_name.set_defaults(func=robot_set_name)
    # Add robot domain id subcommand
    domain_id = TerminalFormatter.color_text(robot_data.domain_id, bold=True)
    parser_robot_domain_id = config_subparsers.add_parser('domain_id', help=f"Set robot domain ID [{domain_id}]")
    parser_robot_domain_id.set_defaults(func=robot_set_domain_id)
    # Add robot simulation subcommand
    device_type = "robot" if platform['Machine'] == 'aarch64' else "desktop"
    if device_type == 'desktop':
        simulation = TerminalFormatter.color_text('simulation' if robot_data.simulation else 'real', bold=True)
        parser_robot_simulation = config_subparsers.add_parser('simulation', help=f"Set robot real or simulation [{simulation}]")
        parser_robot_simulation.set_defaults(func=robot_set_simulation)
    # Add robot camera subcommand
    camera_type = TerminalFormatter.color_text(robot_data.camera_type or 'NOT SELECTED', bold=True)
    parser_robot_camera = config_subparsers.add_parser('camera', help=f"Set robot camera type [{camera_type}]")
    parser_robot_camera.add_argument('--new', type=str, help=f"Specify the new camera type (options: {', '.join(CAMERA_CHOICES)})")
    parser_robot_camera.set_defaults(func=robot_set_camera)
    # Add robot lidar subcommand
    lidar_type = TerminalFormatter.color_text(robot_data.lidar_type or 'NOT SELECTED', bold=True)
    parser_robot_lidar = config_subparsers.add_parser('lidar', help=f"Set robot lidar type [{lidar_type}]")
    parser_robot_lidar.add_argument('--new', type=str, choices=LIDAR_CHOICES, help=f"Specify the new lidar type (options: {', '.join(LIDAR_CHOICES)})")
    parser_robot_lidar.set_defaults(func=robot_set_lidar)
    # Add robot engines subcommand
    engines = TerminalFormatter.color_text(', '.join(robot_data.engines) if robot_data.engines else 'NO ENGINES', bold=True)
    engines_help = f"Configure robot engines [{engines}]"
    parser_robot_engines = config_subparsers.add_parser('engines', help=engines_help)
    parser_robot_engines.add_argument('--new', type=str, help="Specify the new engine configuration")
    parser_robot_engines.set_defaults(func=robot_configure_engines)
    # Add robot reset subcommand
    parser_robot_reset = config_subparsers.add_parser('reset', help="Restore the robot configuration to default")
    parser_robot_reset.set_defaults(func=robot_reset)

    return parser_robot_config


def parser_robot_menu(platform, subparsers: argparse._SubParsersAction, params: Params) -> argparse.ArgumentParser:
    try:
        robot_data = RobotList.current_robot(params)
        robot_name = TerminalFormatter.color_text(robot_data.name, color='green', bold=True)
        parser_robot = subparsers.add_parser('robot', help=f"Manage the Nanosaur robot [{robot_name}]")
        robot_subparsers = parser_robot.add_subparsers(dest='robot_type', help="Robot operations")

        # Add robot start subcommand
        parser_robot_start = robot_subparsers.add_parser('start', help="Activate the robot")
        parser_robot_start.add_argument(
            '--profile', type=str, help="Specify the profile name to use")
        parser_robot_start.add_argument(
            '--detach', action='store_true', help="Run the robot in detached mode")
        parser_robot_start.set_defaults(func=docker.docker_robot_start)
        # Add robot stop subcommand
        parser_robot_stop = robot_subparsers.add_parser('stop', help="Deactivate the robot")
        parser_robot_stop.set_defaults(func=docker.docker_robot_stop)
        # Add robot display subcommand
        parser_robot_display = robot_subparsers.add_parser('rviz', help="Show the robot on rviz")
        parser_robot_display.set_defaults(func=robot_display)
        # Add robot drive subcommand
        parser_robot_drive = robot_subparsers.add_parser('drive', help="Control the robot with keyboard")
        parser_robot_drive.set_defaults(func=control_keyboard)
        # Add robot terminal subcommand
        parser_robot_terminal = robot_subparsers.add_parser('terminal', help="Access the robot with terminal (only docker)")
        parser_robot_terminal.set_defaults(func=control_terminal)
        # Add robot config subcommand
        parser_config = add_robot_config_subcommands(platform, robot_subparsers, params)

        return parser_robot, parser_config
    except IndexError:
        # No robot configured start the wizard
        parser_robot = subparsers.add_parser('robot', help="Initialize a new Nanosaur robot")
        parser_robot.set_defaults(func=wizard)
        return parser_robot, None


def wizard(platform, params: Params, args):
    # Get the device type (robot or desktop)
    device_type = "robot" if platform['Machine'] == 'aarch64' else "desktop"
    # Build the list of functions to run
    functions_list = [robot_set_name] + ([robot_set_simulation] if device_type == 'desktop' else [])
    functions_list += [robot_set_domain_id, robot_set_camera, robot_set_lidar, robot_configure_engines]
    # Set new argument to None
    args.new = None
    # Add a new robot
    robot = Robot()
    robot.simulation = device_type == 'desktop'
    RobotList.add_robot(params, robot, save=False)
    return all(func(platform, params, args) for func in functions_list)


def robot_set_name(platform, params: Params, args):
    """Configure the robot name."""
    robot = RobotList.current_robot(params)

    def validate_name(_, x):
        if not x.isalnum():
            raise inquirer.errors.ValidationError("", reason="Name must contain only letters and numbers")
        return True

    question = [
        inquirer.Text(
            'name',
            message="Enter the new robot name",
            default=robot.name,
            validate=validate_name
        )
    ]

    answers = inquirer.prompt(question, theme=GreenPassion())
    if answers is None:
        return False
    if not answers['name']:
        print(TerminalFormatter.color_text("No name provided", color='red'))
        return False
    new_name = answers['name']
    if new_name != robot.name:
        robot.name = new_name
        RobotList.update_robot(params, robot)
        logger.debug(TerminalFormatter.color_text(f"Robot name set to: {robot.name}", color='green'))
    else:
        logger.debug(TerminalFormatter.color_text(f"Robot name {new_name} is already set", color='yellow'))
    return True


def robot_set_domain_id(platform, params: Params, args):
    """Configure the domain ID."""
    robot = RobotList.current_robot(params)

    def validate_domain_id(_, x):
        if not x.isdigit():
            raise inquirer.errors.ValidationError("", reason="Domain ID must be a number")
        return True

    question = [
        inquirer.Text(
            'domain_id',
            message="Enter the new domain ID",
            default=str(robot.domain_id),
            validate=validate_domain_id
        )
    ]

    answers = inquirer.prompt(question, theme=GreenPassion())
    if answers is None:
        return False
    new_domain_id = int(answers['domain_id'])
    if new_domain_id != robot.domain_id:
        robot.domain_id = new_domain_id
        RobotList.update_robot(params, robot)
        logger.debug(TerminalFormatter.color_text(f"Domain ID set to: {robot.domain_id}", color='green'))
    else:
        logger.debug(TerminalFormatter.color_text(f"Domain ID {new_domain_id} is already set", color='yellow'))
    return True


def robot_set_simulation(platform, params: Params, args):
    """Configure the robot if is real or a simulation."""
    robot = RobotList.current_robot(params)

    question = [
        inquirer.List(
            'simulation',
            message="Is a simulated robot o real robot",
            choices=['simulation', 'real'],
            default='simulation' if robot.simulation else 'real'
        )
    ]

    answers = inquirer.prompt(question, theme=GreenPassion())
    if answers is None:
        return False
    is_simulation = answers['simulation'] == 'simulation'
    robot.simulation = is_simulation
    RobotList.update_robot(params, robot)
    logger.debug(TerminalFormatter.color_text(f"Simulator set to: {answers['simulation']}", color='green'))
    return True


def robot_set_camera(platform, params: Params, args):
    """Configure the camera."""
    robot = RobotList.current_robot(params)

    all_cameras = sorted(set(CAMERA_CHOICES + [robot.camera_type]))

    if args.new is not None:
        if args.new not in all_cameras:
            robot.camera_type = args.new
            RobotList.update_robot(params, robot)
            print(TerminalFormatter.color_text(f"New camera {args.new} selected", color='green'))
        else:
            print(TerminalFormatter.color_text(f"Camera {args.new} is already exist", color='yellow'))
        return True

    options = [
        inquirer.List(
            'camera',
            message="Select a camera",
            choices=[camera or 'No camera' for camera in all_cameras],
            default=robot.camera_type
        )
    ]

    answers = inquirer.prompt(options, theme=GreenPassion())
    if answers is None:
        return False
    selected_camera = answers['camera'].replace(" (selected)", "")

    selected_camera = '' if selected_camera == 'No camera' else selected_camera
    if selected_camera != robot.camera_type:
        robot.camera_type = selected_camera
        RobotList.update_robot(params, robot)
        logger.debug(TerminalFormatter.color_text(f"Camera set to: {robot.camera_type or 'No camera'}", color='green'))
    else:
        logger.debug(TerminalFormatter.color_text(f"Camera {selected_camera or 'No camera'} is already selected", color='yellow'))
    return True


def robot_set_lidar(platform, params: Params, args):
    """Configure the lidar."""
    robot = RobotList.current_robot(params)

    all_lidars = sorted(set(LIDAR_CHOICES + [robot.lidar_type]))

    if args.new is not None:
        if args.new not in all_lidars:
            robot.lidar_type = args.new
            RobotList.update_robot(params, robot)
            logger.debug(TerminalFormatter.color_text(f"New lidar {args.new} selected", color='green'))
        else:
            logger.debug(TerminalFormatter.color_text(f"Lidar {args.new} is already exist", color='yellow'))
        return True

    options = [
        inquirer.List(
            'lidar',
            message="Select a lidar",
            choices=[lidar or 'No lidar' for lidar in all_lidars],
            default=robot.lidar_type
        )
    ]

    answers = inquirer.prompt(options, theme=GreenPassion())
    if answers is None:
        return False
    selected_lidar = answers['lidar'].replace(" (selected)", "")

    selected_lidar = '' if selected_lidar == 'No lidar' else selected_lidar
    if selected_lidar != robot.lidar_type:
        robot.lidar_type = selected_lidar
        RobotList.update_robot(params, robot)
        logger.debug(TerminalFormatter.color_text(f"Lidar set to: {robot.lidar_type or 'No lidar'}", color='green'))
    else:
        logger.debug(TerminalFormatter.color_text(f"Lidar {selected_lidar or 'No lidar'} is already selected", color='yellow'))
    return True


def robot_configure_engines(platform, params: Params, args):
    """Configure the robot engines."""
    robot = RobotList.current_robot(params)

    if args.new is not None:
        if args.new not in robot.engines:
            robot.engines.append(args.new)
            RobotList.update_robot(params, robot)
            print(TerminalFormatter.color_text(f"New engine {args.new} added", color='green'))
        else:
            print(TerminalFormatter.color_text(f"Engine {args.new} is already enabled", color='yellow'))
        return True

    engine_choices = [
        inquirer.Checkbox(
            'engines',
            message="Select engines to enable/disable",
            choices=list(sorted(list(set(robot.engines + ENGINES_CHOICES)))),
            default=robot.engines,
        )
    ]

    answers = inquirer.prompt(engine_choices, theme=GreenPassion())
    if answers is None:
        return False
    robot.engines = answers['engines']
    RobotList.update_robot(params, robot)
    if robot.engines:
        logger.debug(TerminalFormatter.color_text(f"Engines updated: {', '.join(robot.engines)}", color='green'))
    else:
        logger.debug(TerminalFormatter.color_text("No engines selected", color='yellow'))
    return True


def robot_reset(platform, params: Params, args):
    """Reset the robot configuration."""
    # Reset the robot configuration
    RobotList.remove_robot(params)
    print(TerminalFormatter.color_text("Robot configuration reset", color='green'))
    return True


def control_terminal(platform, params: Params, args):
    """Control the robot using the terminal."""
    # Get the robot
    robot = RobotList.current_robot(params)
    if robot.simulation and 'simulation' not in params:
        print(TerminalFormatter.color_text("No simulation tool selected. Please run 'nanosaur simulation set' first.", color='red'))
        return False
    # Run from docker container
    docker.docker_service_run_command(platform, params, "diagnostic", ["bash"], name=f"{robot.name}-terminal")
    return True


def control_keyboard(platform, params: Params, args):
    """Control the robot using the keyboard."""
    # Get the robot
    robot = RobotList.current_robot(params)
    if robot.simulation and 'simulation' not in params:
        print(TerminalFormatter.color_text("No simulation tool selected. Please run 'nanosaur simulation set' first.", color='red'))
        return False
    # Get location starting function (host or docker)
    selected_location = workspace.get_starting_location(params)
    if selected_location is None:
        return False
    # Command to run
    command = f"ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args --remap /cmd_vel:=/{robot.name}/key_vel"
    # Run from local machine
    if selected_location == 'host':
        nanosaur_ws_path = workspace.get_workspace_path(params, 'ws_simulation_name')
        bash_file = f'{nanosaur_ws_path}/install/setup.bash'
        # Read the robot name
        print(TerminalFormatter.color_text(f"Control the robot {robot.name} using the keyboard", color='green'))
        subprocess.run(f'source {bash_file} && {command}', shell=True, executable='/bin/bash')
        return True
    elif selected_location == 'docker':
        # Run from docker container
        docker.docker_service_run_command(platform, params, "diagnostic", shlex.split(command), name=f"{robot.name}-keyboard")
        return True
    else:
        print(TerminalFormatter.color_text(f"Unknown debug mode: {selected_location}", color='red'))
        return False


def robot_display(platform, params: Params, args):
    """Display the robot configuration."""
    # Get location starting function (host or docker)
    selected_location = workspace.get_starting_location(params)
    if selected_location is None:
        return False
    # Get the robot
    robot = RobotList.current_robot(params)
    command = f"ros2 launch nanosaur_visualization robot_display.launch.py robot_name:={robot.name}"
    # Run from local machine
    if selected_location == 'host':
        nanosaur_ws_path = workspace.get_workspace_path(params, 'ws_simulation_name')
        bash_file = f'{nanosaur_ws_path}/install/setup.bash'
        print(TerminalFormatter.color_text(f"Display the robot {robot.name}", color='green'))
        try:
            subprocess.run(f'source {bash_file} && {command}', shell=True, executable='/bin/bash')
        except KeyboardInterrupt:
            print(TerminalFormatter.color_text("Keyboard interrupt received, stopping robot display", color='yellow'))
        return True
    elif selected_location == 'docker':
        # Run from docker container
        docker.docker_service_run_command(platform, params, "diagnostic", shlex.split(command), name=f"{robot.name}-rviz")
        return True
    else:
        print(TerminalFormatter.color_text(f"Unknown debug mode: {selected_location}", color='red'))
        return False
# EOF
