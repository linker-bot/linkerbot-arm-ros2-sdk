# LinkerBot Arm ROS2

[中文](README.md)

Control left and right LinkerBot A7, A7 Lite, and P7 arms through ROS2 topics and services, using the standalone `linkerbot-arm` SDK. Supports Ubuntu 22.04 / Humble / Python 3.10 and Ubuntu 24.04 / Jazzy / Python 3.12.

## Getting Started

1. [Installation and Build](docs/en/INSTALLATION.md): create the matching ROS Python environment and install the paired SDK.
2. [Connecting and Starting](docs/en/getting_started.md): configure CAN, choose a model, and launch one or both arms.
3. [Topics and Joint Control](docs/en/topics.md): read state and publish seven-joint targets.

The [Developer User Manual](docs/en/environment_setup.md) covers configuration, lifecycle services, feedback timestamps, calibration, troubleshooting, and [Docker validation](docs/en/testing.md).

The ROS2 package and Python import remain `linker_arm_ros2`. Install the SDK/transport from this repository's [source manifest](requirements/source-versions.txt); transport uses current `main` without a version or tag constraint. The default configuration automatically enables and homes at startup; follow the first-session guide to disable automatic enabling initially.

## Development and Validation

Humble/Jazzy share the node, launch files, and configuration. See [Testing and Docker Validation](docs/en/testing.md) for checks. Tests without hardware do not validate physical motion, stopping, or calibration.

Source: [linker-bot/linkerbot-arm-ros2](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2). See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow.
