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

# flake8: noqa

__author__ = "Raffaello Bonghi"
__email__ = "raffaello@rnext.it"
__cr__ = "(c) 2025, RB"
__copyright__ = "(c) 2025, Raffaello Bonghi"
# Version package
# https://packaging.python.org/guides/distributing-packages-using-setuptools/#choosing-a-versioning-scheme
__version__ = "0.1.4"

from .main import install  # noqa: F401
from .ros import rosinstall_reader  # noqa: F401
from .utilities import Params, RobotList, Robot, get_nanosaur_home, get_nanosaur_docker_user  # noqa: F401
from .workspace import (
    get_selected_workspace,
    get_workspaces_path,
    get_shared_workspace_path,
    deploy)  # noqa: F401
from .prompt_colors import TerminalFormatter  # noqa: F401
from .variables import (NANOSAUR_DISTRO_MAP,
    NANOSAUR_CURRENT_DISTRO,
    NANOSAUR_DOCKER_PACKAGE)  # noqa: F401
# EOF
