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

import subprocess
from nanosaur import workspace
from nanosaur.prompt_colors import TerminalFormatter
from nanosaur.utilities import Params, RobotList

# Dictionary of simulation tools and their commands
simulation_tools = {
    "Isaac Sim": {
        "simulator": "ros2 launch isaac_sim_wrapper isaac_sim_server.launch.py",
        "robot": "ros2 launch nanosaur_isaac_sim nanosaur_bridge.launch.py"
    },
    "Gazebo": {
        "simulator": "ros2 launch nanosaur_gazebo gazebo.launch.py",
        "robot": "ros2 launch nanosaur_gazebo nanosaur_bridge.launch.py"
    }
}


def start_robot_simulation(params):
    nanosaur_ws_path = workspace.get_workspace_path(params, params['ws_simulation_name'])
    bash_file = f'{nanosaur_ws_path}/install/setup.bash'
    # Check which simulation tool is selected
    if 'simulation_tool' not in params:
        print(TerminalFormatter.color_text("No simulation tool selected. Please run simulation set first.", color='red'))
        return False
    # Check if the simulation tool is valid and get the command
    command = simulation_tools[params['simulation_tool']]['robot']
    # Load the robot configuration
    robot = RobotList.get_robot(params)
    print(TerminalFormatter.color_text(f"Starting {robot}", color='green'))

    # Print the command to be run
    print(f"ROS_DOMAIN_ID={robot.domain_id} {command} {robot.config_to_ros()}")    

    try:
        # Combine sourcing the bash file with running the command
        process = subprocess.Popen(
            f"source {bash_file} && ROS_DOMAIN_ID={robot.domain_id} {command} {robot.config_to_ros()}",
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
    """Install the simulation tools."""

    nanosaur_ws_path = workspace.get_workspace_path(params, params['ws_simulation_name'])
    bash_file = f'{nanosaur_ws_path}/install/setup.bash'
    # Check which simulation tool is selected
    if 'simulation_tool' not in params:
        print(TerminalFormatter.color_text("No simulation tool selected. Please run simulation set first.", color='red'))
        return False

    if params['simulation_tool'] not in simulation_tools:
        print(TerminalFormatter.color_text(f"Unknown simulation tool: {params['simulation_tool']}", color='red'))
        return False

    command = simulation_tools[params['simulation_tool']]['simulator']

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


def simulation_set(platform, params: Params, args):
    """Set the simulation tools."""
    while True:
        print("Set the simulation tools:")
        # List of simulation environments
        sim_options = list(simulation_tools.keys())

        # Print options from list
        for i, value in enumerate(sim_options, 1):
            if 'simulation_tool' in params and params['simulation_tool'] == value:
                print(f"{i}. {TerminalFormatter.color_text(value, color='green')} [Current]")
            else:
                print(f"{i}. {value}")
        exit_option = len(sim_options) + 1
        print(f"{exit_option}. Exit")

        try:
            choice = input("Enter your choice: ")
        except KeyboardInterrupt:
            print(TerminalFormatter.color_text("Exiting...", color='yellow'))
            return False

        if choice.isdigit():
            choice_num = int(choice)
            if choice_num == exit_option:
                # print(TerminalFormatter.color_text("Exiting...", color='yellow'))
                break
            elif 1 <= choice_num <= len(sim_options):
                params['simulation_tool'] = sim_options[choice_num - 1]
                print(TerminalFormatter.color_text(f"Selected {sim_options[choice_num - 1]}", color='green'))
                break
            else:
                print(TerminalFormatter.color_text(f"Invalid choice. Please enter a number between 1 and {exit_option}.", color='red'))
        else:
            print(TerminalFormatter.color_text("Invalid choice. Please enter a number.", color='red'))
    return True
# EOF
