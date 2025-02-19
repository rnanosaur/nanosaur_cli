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
import sys
import pexpect
import subprocess
import pty
import select
import termios
import tty
import signal
import shutil
import logging
import yaml
import urllib.parse
from python_on_whales import docker, DockerException
from nanosaur.prompt_colors import TerminalFormatter
from nanosaur.utilities import get_nanosaur_home, Robot
from git import Repo, GitCommandError

# Set up the logger
logger = logging.getLogger(__name__)

ISAAC_ROS_COMMON_FOLDER = 'isaac_ros_common'
ISAAC_ROS_COMMON_REPO = 'https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common'


def get_ros2_path(version, folder="/opt/ros"):
    """Check if a specific ROS 2 version is installed and return its path."""
    version_path = os.path.join(folder, version)
    return version_path if os.path.isdir(version_path) else None


def run_docker_ros(docker_image):

    docker.run(docker_image, command="bash")


def run_docker_isaac_ros(workspace_path: str, robot: Robot, auto_commands=[]):
    nanosaur_home_path = get_nanosaur_home()
    # Path to the Isaac ROS common package
    isaac_ros_common_path = os.path.join(nanosaur_home_path, ISAAC_ROS_COMMON_FOLDER)

    # Path to the script you want to run
    command = "./scripts/run_dev.sh"
    # Build the command arguments
    # TODO: Add commands '-a', f"-e NANOSAUR_COMMANDS={robot.config_to_ros()}"
    args = ["-d", workspace_path, '-a', f"-v {nanosaur_home_path}/shared_src:/workspaces/shared_src"]
    # Get the path to the Isaac ROS common package
    os.chdir(isaac_ros_common_path)
    logger.debug(f"Changed directory to: {isaac_ros_common_path}")

    # Check if .isaac_ros_common-config exists and remove it
    config_path = os.path.join(isaac_ros_common_path, 'scripts', '.isaac_ros_common-config')
    if os.path.exists(config_path):
        os.remove(config_path)
        logger.debug(TerminalFormatter.color_text(f"Removed existing config file: {config_path}", color='yellow'))

    # Save the original terminal settings
    original_termios = termios.tcgetattr(sys.stdin)

    def set_raw_mode():
        """Set terminal to raw mode to handle special characters."""
        tty.setraw(sys.stdin.fileno())

    def restore_terminal():
        """Restore original terminal settings."""
        termios.tcsetattr(sys.stdin, termios.TCSANOW, original_termios)

    def handle_signal(signum, frame):
        """Forward terminal signals to the subprocess."""
        os.kill(child_pid, signum)

    # Open a pseudo-terminal
    master_fd, slave_fd = pty.openpty()

    # Prepare the command and arguments
    cmd = [command] + (args or [])

    # Fork the process
    child_pid = os.fork()
    if child_pid == 0:  # Child process
        os.close(master_fd)  # Close master in the child process
        os.dup2(slave_fd, sys.stdin.fileno())  # Use slave as stdin
        os.dup2(slave_fd, sys.stdout.fileno())  # Use slave as stdout
        os.dup2(slave_fd, sys.stderr.fileno())  # Use slave as stderr
        os.execvp(cmd[0], cmd)  # Execute the command
    else:  # Parent process
        os.close(slave_fd)  # Close slave in the parent process

    try:
        set_raw_mode()

        # Forward terminal signals to the subprocess
        for sig in (signal.SIGINT, signal.SIGTSTP, signal.SIGQUIT):
            signal.signal(sig, handle_signal)

        # Automatically send commands if specified
        if auto_commands:
            for command in auto_commands:
                os.write(master_fd, (command + '\n').encode())

        while True:
            # Wait for input from the user or output from the subprocess
            rlist, _, _ = select.select([sys.stdin, master_fd], [], [])

            if sys.stdin in rlist:  # User input
                user_input = os.read(sys.stdin.fileno(), 1024)
                os.write(master_fd, user_input)  # Forward input to the subprocess

            if master_fd in rlist:  # Subprocess output
                try:
                    output = os.read(master_fd, 1024)
                    if not output:  # If the subprocess exits, stop the loop
                        break
                    # Filter and render subprocess output to avoid cursor resets
                    filtered_output = output.replace(b"\x1b[2J", b"")  # Remove clear screen sequences
                    sys.stdout.buffer.write(filtered_output)
                    sys.stdout.buffer.flush()
                except OSError as e:
                    if e.errno == 5:  # Input/output error
                        break
                    else:
                        raise
    finally:
        restore_terminal()  # Restore the original terminal settings
        os.close(master_fd)

    print(TerminalFormatter.color_text("Dev script finished", color='green'))


def rosinstall_reader(workspace_path, rosinstall_path, src_folder="src", tag_version=None, token=None) -> bool:
    folder_path = os.path.join(workspace_path, src_folder)
    if not os.path.exists(folder_path):
        print(TerminalFormatter.color_text(f"Error: Folder {folder_path} does not exist.", color='red'))
        return False
    # Load the YAML file
    with open(rosinstall_path, 'r') as file:
        repos = yaml.safe_load(file)
    # Iterate over the repositories in the YAML file
    for repo in repos:
        if git_info := repo.get('git'):
            # Fetch the details from the YAML
            local_name = git_info.get('local-name')
            version = git_info.get('version', 'main')  # Default to 'main' if no version is provided
            if tag_version:
                version = tag_version
                print(TerminalFormatter.color_text(f"Warning: Overriding tag version with {tag_version}", color='yellow'))
            uri = git_info.get('uri')

            # Ensure that local_name is always defined
            if not local_name:
                # Extract the repository name from the URI (the last part of the URL)
                parsed_uri = urllib.parse.urlparse(uri)
                local_name = os.path.splitext(os.path.basename(parsed_uri.path))[0]
        # If the repo does not exist, clone it
        repo_path = os.path.join(folder_path, local_name)
        print(f"=== {os.path.abspath(local_name)} ({uri}) ===")
        if not os.path.exists(repo_path):
            print(f"Cloning {repo_path}...")
            new_uri = uri
            if token is not None:
                print(TerminalFormatter.color_text("Using token for authentication", color='yellow'))
                new_uri = uri.replace("https://", f"https://{token['username']}:{token['password']}@", 1)
            # Clone the repository
            repo_dir = Repo.clone_from(new_uri, repo_path, branch=version)
            if token is not None:
                # Remove the token from the URL
                repo_dir.remotes.origin.set_url(uri)
        else:
            try:
                # Open the existing repo and fetch the latest changes
                repo_dir = Repo(repo_path)
                original_remote_url = repo_dir.remotes.origin.url
                if token is not None:
                    print(TerminalFormatter.color_text("Using token for authentication", color='yellow'))
                    authenticated_remote_url = original_remote_url.replace("https://", f"https://{token['username']}:{token['password']}@", 1)
                else:
                    authenticated_remote_url = original_remote_url
                # Fetch the latest changes
                repo_dir.git.fetch(authenticated_remote_url)
                # Checkout the specified version (branch or tag)
                repo_dir.git.checkout(version)
                # Check if there are any modified files
                if modified_files := repo_dir.git.diff('--name-only'):
                    print(f"\nAlready on '{version}'")
                    for file in modified_files.splitlines():
                        print(TerminalFormatter.color_text(f"M\t{file}", color='yellow'))
                if token is not None:
                    # Remove the token from the URL
                    repo_dir.remotes.origin.set_url(original_remote_url)
                else:
                    print(f"\nAlready on '{version}'")
                print(f"Your branch is up to date with 'origin/{version}'.")
            except GitCommandError:
                print(f"Error: Version {version} not found in {local_name}.")
                return False
    return True


def run_vcs_import(workspace_path, rosinstall_path, src_folder="src") -> bool:
    """
    Run the vcs import command to import repositories into a ROS workspace.
    NOT USED ANYMORE, now we use the rosinstall_reader function.
    """
    try:
        # Run the command and stream the output live
        process = subprocess.Popen(
            f"vcs import {workspace_path}/{src_folder} < {rosinstall_path}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Stream output live
        for line in process.stdout:
            print(line.decode('utf-8'), end="")  # Print stdout line-by-line

        # Wait for the process to finish
        process.wait()

        # Stream any errors
        for line in process.stderr:
            print(TerminalFormatter.color_text(line.decode('utf-8'), color='red'), end="")  # Print stderr (errors) in red

        # Check the exit status of the command
        if process.returncode != 0:
            print(TerminalFormatter.color_text(process.returncode, color='red'))
        else:
            print(TerminalFormatter.color_text("Command completed successfully", color='green'))

        return process.returncode == 0

    except Exception as e:
        print(f"An error occurred while running the command: {e}")
        return False


def run_rosdep(ros2_path, folder_path, shared_src_path) -> bool:
    try:
        ros2_setup_path = os.path.join(ros2_path, 'setup.bash')
        command = f"source {ros2_setup_path} && rosdep install --from-paths {folder_path}/src {shared_src_path} --ignore-src -r -y"
        process = subprocess.Popen(
            command,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Stream output live
        for line in process.stdout:
            print(line.decode('utf-8'), end="")  # Print stdout line-by-line

        # Wait for the process to finish
        process.wait()

        # Stream any errors
        for line in process.stderr:
            print(TerminalFormatter.color_text(line.decode('utf-8'), color='red'), end="")  # Print stderr (errors) in red

        # Check the exit status of the command
        if process.returncode != 0:
            print(TerminalFormatter.color_text(process.returncode, color='red'))
            return False
        else:
            print(TerminalFormatter.color_text("Command completed successfully", color='green'))
            return True

    except Exception as e:
        print(f"An error occurred while running the rosdep command: {e}")
        return False


def run_colcon_build(ros2_path, folder_path) -> bool:

    # Move to the folder_path and run the colcon build command
    try:
        os.chdir(folder_path)
        print(f"Changed directory to: {folder_path}")
        ros2_setup_path = os.path.join(ros2_path, 'setup.bash')
        # Run the command and stream the output live
        process = subprocess.Popen(
            f"source {ros2_setup_path} && colcon build --symlink-install --merge-install",
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Stream output live
        for line in process.stdout:
            print(line.decode('utf-8'), end="")  # Print stdout line-by-line

        # Wait for the process to finish
        process.wait()

        # Stream any errors
        for line in process.stderr:
            print(TerminalFormatter.color_text(line.decode('utf-8'), color='red'), end="")  # Print stderr (errors) in red

        # Check the exit status of the command
        if process.returncode != 0:
            print(TerminalFormatter.color_text(process.returncode, color='red'))
        else:
            print(TerminalFormatter.color_text("Command completed successfully", color='green'))

        return process.returncode == 0

    except Exception as e:
        print(f"An error occurred while running the colcon build command: {e}")
        return False


def deploy_docker_image(dockerfile_path, tag_image, platforms=None) -> bool:
    try:
        print(TerminalFormatter.color_text(f"Building Docker image {tag_image}", color='magenta', bold=True))
        if platforms:
            print(TerminalFormatter.color_text(f"- for platforms: {platforms}", color='magenta', bold=True))
        docker.build(
            get_nanosaur_home(),
            file=dockerfile_path,
            tags=tag_image,
            platforms=platforms,
        )
        print(TerminalFormatter.color_text("Docker image built successfully", color='green'))
        return True
    except DockerException as e:
        print(TerminalFormatter.color_text(f"Error building Docker image: {e}", color='red'))
        return False


def deploy_docker_isaac_ros(isaac_ros_ws_path, tags, release_tag_name, debug=False) -> bool:
    """
    Deploys the Isaac ROS Docker image.

    Args:
        isaac_ros_ws_path (str): Path to the Isaac ROS workspace.
        tags (list): List of tags for the Docker image.
        release_tag_name (str): Release tag name for the Docker image.
        debug (bool): Flag to enable debug mode.

    Returns:
        bool: True if the deployment is successful, False otherwise.
    """
    # Define shared source path
    shared_path = os.path.join(get_nanosaur_home(), 'shared_src')
    src_path = os.path.join(isaac_ros_ws_path, 'src')
    # Check if src_path is not empty
    if not os.listdir(src_path):
        print(TerminalFormatter.color_text(f"Error: Source path {isaac_ros_ws_path} is empty.", color='red'))
        return False
    # List of source folders to include in the workspace
    src_folders = [
        shared_path,
        src_path,
    ]
    ws_dir_list = '--ws-src ' + ' --ws-src '.join(src_folders)
    # Path to the Isaac ROS common package
    isaac_ros_common_path = os.path.join(get_nanosaur_home(), ISAAC_ROS_COMMON_FOLDER)
    # Path to the Nanosaur Docker scripts
    nanosaur_docker_path = os.path.join(shared_path, 'nanosaur', 'nanosaur', 'docker')
    # Build the command to run the Docker build script
    debug_flag = '--debug' if debug else ''
    tags_name = '.'.join(tags)
    command = f"{nanosaur_docker_path}/docker_build_isaac_ros.sh {debug_flag} -d {tags_name} -c {isaac_ros_common_path} -i {release_tag_name} {ws_dir_list}"

    try:
        print(TerminalFormatter.color_text(f"Deploying {release_tag_name}", color='magenta', bold=True))
        # Run the command and stream the output live
        process = subprocess.Popen(
            command,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        # Stream output live
        for line in process.stdout:
            print(line.decode('utf-8', errors='replace'), end="")
        # Wait for the process to finish
        process.wait()
        # Check the exit status of the command
        if process.returncode != 0:
            print(TerminalFormatter.color_text(f"Command failed with return code: {process.returncode}", color='red'))
            return False
        else:
            print(TerminalFormatter.color_text("Command completed successfully", color='green'))
            return True
    except KeyboardInterrupt:
        print(TerminalFormatter.color_text("Process interrupted by user", color='red'))
        process.terminate()
        process.wait()
        return False
    except Exception as e:
        print(f"An error occurred while running the command: {e}")
        return False


def manage_isaac_ros_common_repo(nanosaur_home_path: str, isaac_ros_branch: str, force) -> bool:
    # Path to the Isaac ROS common package
    isaac_ros_common_path = os.path.join(nanosaur_home_path, ISAAC_ROS_COMMON_FOLDER)

    def update_existing_repo():
        try:
            print(TerminalFormatter.color_text(f"Directory '{isaac_ros_common_path}' already exists. Pulling latest changes from branch '{isaac_ros_branch}'.", color='yellow'))
            repo = Repo(isaac_ros_common_path)
            repo.git.checkout(isaac_ros_branch)
            repo.remotes.origin.pull()
            print(TerminalFormatter.color_text("Repository updated successfully", color='green'))
            return True
        except GitCommandError as e:
            print(TerminalFormatter.color_text(f"Error updating repository: {e}", color='red'))
            return False

    def clone_new_repo():
        try:
            print(TerminalFormatter.color_text(f"Cloning isaac_ros_common into '{isaac_ros_common_path}' from branch '{isaac_ros_branch}'", color='magenta', bold=True))
            Repo.clone_from(ISAAC_ROS_COMMON_REPO, isaac_ros_common_path, branch=isaac_ros_branch)
            print(TerminalFormatter.color_text("Clone completed successfully", color='green'))
            return True
        except GitCommandError as e:
            print(TerminalFormatter.color_text(f"Error cloning repository from branch '{isaac_ros_branch}': {e}", color='red'))
            return False

    # Check if the Isaac ROS common package already exists
    if os.path.exists(isaac_ros_common_path):
        if force:
            print(TerminalFormatter.color_text(f"Deleting existing directory '{isaac_ros_common_path}'.", color='yellow'))
            shutil.rmtree(isaac_ros_common_path)
        return update_existing_repo()
    else:
        return clone_new_repo()
# EOF
