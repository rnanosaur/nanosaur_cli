# Changelog

## [0.1.4]

### Features

- Redesign the simulation tool
- New diagnostic docker multi-platform
- Added new function in `nanosaur robot terminal` to launch a terminal from docker
- Added new function in `nanosaur robot world` to select a world to load
- Improve `nanosaur info` now show all services if are running
- Added new function `nanosaur update` that update the `nanosaur-cli` and pull all latest docker images
- Improve `nanosaur ws deploy` with hidden commands to push and build a release

### Fixes

- Improve `sudo` request for `nanosaur ws build`

## [0.1.3] - 2025-02-15

### Features

- Show nanosaur CLI version in `nanosaur info`
- ROS 2 build is disable in maintainer install
- Only one `docker-compose.yml` for simulation and real robot
- now `rosinstall_reader(.)` clone also from private repository

### Fixes

- Minor fixes

## [0.1.2] - 2025-02-12

### Fixes

- Improve Discord notification message

## [0.1.1] - 2025-02-12

### Fixes

- Fix Lint CI for release
- Add publish message on Discord

## [0.1.0] - 2025-02-12

First functional release of nanosaur CLI

### Features

- Update CLI to works with nanosaur in simulation
- swarm control
- robot configuration
- Start simulation for Gazebo and Isaac Sim
- ROS workspace control
- Docker deploy

## [0.0.1] - 2024-10-21

### Features

- First code release and publish of nanosaur cli package
