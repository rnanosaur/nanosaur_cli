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

# https://gabrieldemarmiesse.github.io/python-on-whales/
import os
import logging
import subprocess
from python_on_whales import docker, DockerClient, DockerException
from nanosaur.utilities import Params, RobotList, get_nanosaur_home, build_env_file
from nanosaur.prompt_colors import TerminalFormatter
from datetime import datetime

# Set up the logger
logger = logging.getLogger(__name__)


def format_time_delta(delta):
    if delta.days > 0:
        return f"{delta.days} days ago"
    hours, remainder = divmod(delta.seconds, 3600)
    if hours > 0:
        return f"{hours} hours ago"
    minutes, _ = divmod(remainder, 60)
    if minutes > 0:
        return f"{minutes} minutes ago"
    return "just now"


def docker_info(params, verbose):
    """Display information about running Docker services."""
    nanosaur_home_path = get_nanosaur_home()
    robot = RobotList.current_robot(params)
    docker_compose_path = os.path.join(nanosaur_home_path, "docker-compose.yml")
    env_file_path = os.path.join(nanosaur_home_path, f'{robot.name}.env')
    nanosaur_compose = DockerClient(compose_files=[docker_compose_path], compose_env_files=[env_file_path])

    # Get the list of all services, including stopped ones
    running_services = nanosaur_compose.compose.ps(all=True)
    if not running_services:
        print(TerminalFormatter.color_text("No services are currently running.", bold=True))
        return

    print(TerminalFormatter.color_text("Running services:", bold=True))
    for service in running_services:
        # Map the service status to an emoji
        status_emoji = {
            "running": "✅",
            "restarting": "🔄",
            "paused": "⏸️",
            "dead": "💀"
        }.get(service.state.status, "❌")

        # Calculate the time since the service was started
        started_at = datetime.now(service.state.started_at.tzinfo) - service.state.started_at
        started_at_str = format_time_delta(started_at)

        # Calculate the time since the service was finished, if applicable
        finished_at_str = "N/A"
        if service.state.finished_at:
            finished_at = datetime.now(service.state.finished_at.tzinfo) - service.state.finished_at
            finished_at_str = format_time_delta(finished_at)

        # Determine the time status based on whether the service is running
        if service.state.status == "running":
            time_status = f"{TerminalFormatter.color_text('Created: ', bold=True)} {started_at_str}"
        else:
            time_status = f"{TerminalFormatter.color_text('Finished:', bold=True)} {finished_at_str}"

        # Print the service information
        print(f"  - [{status_emoji}] {TerminalFormatter.color_text('Service:', bold=True)} {service.name:<35} {time_status}")


def docker_version_info(platform):
    """Print Docker information."""
    # Print docker information
    version_info = docker.version()
    print(f"{TerminalFormatter.color_text('   Docker version:', bold=True)} {version_info.client.version}")
    if docker.buildx.is_installed():
        version = docker.buildx.version().split(' ')[-2]
        print(f"{TerminalFormatter.color_text('   Docker buildx:', bold=True)} {version}")
    else:
        print(f"{TerminalFormatter.color_text('   Docker buildx:', bold=True)} {TerminalFormatter.color_text('not installed', color='red', bold=True)}")
    if docker.compose.is_installed():
        version = docker.compose.version().split(' ')[-1]
        print(f"{TerminalFormatter.color_text('   Docker compose:', bold=True)} {version}")
    else:
        print(f"{TerminalFormatter.color_text('   Docker compose:', bold=True)} {TerminalFormatter.color_text('not installed', color='red', bold=True)}")

    if version := check_nvidia_container_cli():
        print(f"{TerminalFormatter.color_text('   NVIDIA container:', bold=True)} {version}")
    else:
        print(f"{TerminalFormatter.color_text('   NVIDIA container:', bold=True)} {TerminalFormatter.color_text('not installed', color='red', bold=True)}")


def is_docker_installed():
    if not docker.compose.is_installed():
        print(TerminalFormatter.color_text("Please install Docker and Docker Compose.", color='red'))
        return False
    if not check_nvidia_container_cli():
        print(TerminalFormatter.color_text("Please install Nvidia container CLI.", color='red'))
        return False
    return True


def check_nvidia_container_cli():
    try:
        # Run the command and capture the output
        result = subprocess.run(
            ["nvidia-container-cli", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0:
            return result.stdout.splitlines()[0].split(' ')[-1]  # Return the first line of the version string
        logger.debug(TerminalFormatter.color_text("Error:", color='red'), result.stderr.strip())
        return None

    except FileNotFoundError:
        logger.debug(TerminalFormatter.color_text("Error: nvidia-container-cli is not installed or not in the PATH.", color='red'))
        return None
    except Exception as e:
        logger.debug(TerminalFormatter.color_text(f"An unexpected error occurred: {e}", color='red'))
        return None


def docker_service_run_command(platform, params: Params, service, command=None, name=None, volumes=None):
    """Run a command in the robot container."""

    if command is None:
        command = []
    if volumes is None:
        volumes = []
    nanosaur_home_path = get_nanosaur_home()
    # Create the full file path
    robot = RobotList.current_robot(params)
    docker_compose_path = os.path.join(nanosaur_home_path, "docker-compose.yml")
    env_file_path = os.path.join(nanosaur_home_path, f'{robot.name}.env')

    # Build env file
    build_env_file(params)
    # Create a DockerClient object with the docker-compose file
    nanosaur_compose = DockerClient(compose_files=[docker_compose_path], compose_env_files=[env_file_path])
    print(TerminalFormatter.color_text(f"Running command in the robot {robot.name} container", color='green'))
    try:
        nanosaur_compose.compose.run(service=service, command=command, remove=True, tty=True, name=name, volumes=volumes)
    except DockerException as e:
        print(TerminalFormatter.color_text(f"Error running the command: {e}", color='red'))
        return False
    return True


def docker_robot_start(platform, params: Params, args):
    """Start the docker container."""
    nanosaur_home_path = get_nanosaur_home()
    # Create the full file path
    robot = RobotList.current_robot(params)
    docker_compose_path = os.path.join(nanosaur_home_path, "docker-compose.yml")
    env_file_path = os.path.join(nanosaur_home_path, f'{robot.name}.env')

    # Check which simulation tool is selected only if robot.simulation is true
    if robot.simulation and 'simulation' not in params:
        print(TerminalFormatter.color_text("No simulation tool selected. Please run 'nanosaur simulation set' first.", color='red'))
        return False

    # Build env file
    build_env_file(params)

    print(TerminalFormatter.color_text(f"robot {robot.name} starting", color='green'))

    compose_profiles = []
    if args.profile:
        print(TerminalFormatter.color_text(f"Starting with profile: {args.profile}", color='green'))
        compose_profiles = [args.profile]
    # Create a DockerClient object with the docker-compose file
    nanosaur_compose = DockerClient(compose_files=[docker_compose_path], compose_env_files=[env_file_path], compose_profiles=compose_profiles)
    # Start the container in detached mode
    try:
        nanosaur_compose.compose.up(detach=args.detach)
        if not args.detach:
            nanosaur_compose.compose.rm(volumes=True)
    except DockerException as e:
        print(TerminalFormatter.color_text(f"Error starting the robot: {e}", color='red'))
        return False


def docker_simulator_start(platform, params: Params, args):
    """Start the simulation tools."""
    nanosaur_home_path = get_nanosaur_home()
    # Create the full file path
    robot = RobotList.current_robot(params)
    docker_compose_path = os.path.join(nanosaur_home_path, "docker-compose.yml")
    env_file_path = os.path.join(nanosaur_home_path, f'{robot.name}.env')

    # Get the simulation data from the parameters
    simulation_data = params.get('simulation', {})
    # Start the container in detached mode
    simulation_tool = simulation_data['tool'].lower().replace(' ', '-')
    # Create a DockerClient object with the docker-compose file
    nanosaur_compose = DockerClient(compose_files=[docker_compose_path], compose_env_files=[env_file_path])

    # if len(nanosaur_compose.compose.ps()) > 0:
    #    print(TerminalFormatter.color_text(f"The robot {robot.name} is already running.", color='red'))
    #    return False

    # Build env file
    build_env_file(params)

    print(TerminalFormatter.color_text(f"Simulator {simulation_tool} starting", color='green'))
    try:
        nanosaur_compose.compose.up(services=[f'{simulation_tool}'], recreate=False)
        nanosaur_compose.compose.rm(services=[f'{simulation_tool}'], volumes=True)
    except DockerException as e:
        print(TerminalFormatter.color_text(f"Error starting the simulation tool: {e}", color='red'))
        return False


def docker_robot_stop(platform, params: Params, args):
    """Stop the docker container."""
    nanosaur_home_path = get_nanosaur_home()
    # Create the full file path
    robot = RobotList.current_robot(params)
    docker_compose_path = os.path.join(nanosaur_home_path, "docker-compose.yml")
    env_file_path = os.path.join(nanosaur_home_path, f'{robot.name}.env')

    # Create a DockerClient object with the docker-compose file
    nanosaur_compose = DockerClient(compose_files=[docker_compose_path], compose_env_files=[env_file_path])
    if len(nanosaur_compose.compose.ps()) > 0:
        nanosaur_compose.compose.down(volumes=True)
        print(TerminalFormatter.color_text(f"robot {robot.name} stopped", color='green'))
    else:
        print(TerminalFormatter.color_text(f"The robot {robot.name} is not running.", color='red'))
# EOF
