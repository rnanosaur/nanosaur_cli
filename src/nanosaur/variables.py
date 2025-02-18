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


NANOSAUR_DISTRO_MAP = {
    '2.0.0': {
        'nanosaur_branch': 'nanosaur2',
        'ros': 'humble',
        'isaac_ros_release': 'release-3.2',
        'isaac_ros_distro': 'ros2_humble',
        'isaac_sim': '>=4.1, <=4.5',
    },
}
NANOSAUR_CURRENT_DISTRO = '2.0.0'

ISAAC_ROS_DOCKER_CAMERA_LIST = ["realsense", "zed"]
NANOSAUR_DOCKERFILE_SUFFIX = "nanosaur"

DEFAULT_WORKSPACE_PERCEPTION = 'perception_ws'
DEFAULT_WORKSPACE_SIMULATION = 'simulation_ws'
DEFAULT_WORKSPACE_ROBOT = 'robot_ws'
DEFAULT_WORKSPACE_DEVELOPER = 'ros_ws'

NANOSAUR_SIMULATION_IMAGES = ['gazebo', 'isaac-sim', 'nanosaur']

NANOSAUR_DOCKER_PACKAGE = {
    'simulation': {
        'x86_64': ['simulation:gazebo', 'simulation:isaac-sim', 'nanosaur:simulation'],
        'aarch64': [],
    },
    'perception': {
        'x86_64': ['perception:simulation'],
        'aarch64': ['perception:realsense', 'perception:zed'],
    },
    'robot': {
        'x86_64': [],
        'aarch64': ['nanosaur:robot'],
    },
    'diagnostic': {
        'x86_64': ['nanosaur:diagnostic'],
        'aarch64': ['nanosaur:diagnostic'],
    }
}
# EOF
