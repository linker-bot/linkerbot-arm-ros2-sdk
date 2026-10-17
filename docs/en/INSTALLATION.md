# Installation and Build

## 1. Choose a ROS2 Distribution

Use **Humble / Python 3.10** on Ubuntu 22.04, or **Jazzy / Python 3.12** on Ubuntu 24.04. Install ROS2 and configure its APT repository using the official [Humble](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) or [Jazzy](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) instructions. The commands below use Bash.

Use a separate terminal, venv, and workspace for each distribution. Do not source both distributions together or reuse another distribution's `build/`, `install/`, or `log/` directories.

## 2. Get the Source

```bash
mkdir -p ~/linkerbot_ws/src
git clone --branch main https://github.com/linker-bot/linkerbot-arm-ros2-sdk.git ~/linkerbot_ws/src/linkerbot-arm-ros2
```

The following commands assume this workspace. For an existing checkout, set `ARM_ROS_SOURCE` to its actual path.

## 3. Create the Python Environment

```bash
ARM_ROS_DISTRO=humble  # Use jazzy on Ubuntu 24.04
sudo apt update
sudo apt install python3-venv python3-pip python3-colcon-common-extensions "ros-${ARM_ROS_DISTRO}-pinocchio"
source "/opt/ros/${ARM_ROS_DISTRO}/setup.bash"
/usr/bin/python3 -m venv --system-site-packages "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}"
source "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}/bin/activate"

ARM_ROS_SOURCE="$HOME/linkerbot_ws/src/linkerbot-arm-ros2"
ARM_CONSTRAINTS=$(python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py" --print-constraints)
python -m pip install --upgrade -c "$ARM_CONSTRAINTS" 'pip<26' setuptools wheel 'packaging>=24.2'
```

The environment check validates Ubuntu, ROS, Python, the venv, and real ROS imports. If it fails, correct the environment before continuing.

Both profiles use NumPy 1.26.4, SciPy 1.13.1, and setuptools `>=77,<80`. Pinocchio/eigenpy come from the matching ROS APT packages. Humble's system NumPy is below the SDK requirement; install the profile's version.

The SDK requires Pinocchio when constructing an arm, including for joint-only control. Install the base SDK **without `[kinetix]`** in this setup to avoid mixing PyPI `pin` with the APT numerical libraries.

<a id="paired-sdk"></a>

## 4. Install the Latest SDK

The ROS2 [source manifest](https://github.com/linker-bot/linkerbot-arm-ros2-sdk/blob/main/requirements/source-versions.txt) installs the latest SDK and Transport sources from `main`.

```bash
python -m pip install --force-reinstall -c "$ARM_CONSTRAINTS" \
  -r "$ARM_ROS_SOURCE/requirements/source-versions.txt"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

The manifest obtains source dependencies over GitHub HTTPS. `--force-reinstall` also refreshes existing SDK and Transport installations to the latest `main`, even if their version numbers have not changed.

For editable installations, clone the GitHub sources first. The dependency directories below must not already exist:

```bash
mkdir -p ~/linkerbot-deps
git clone --branch main https://github.com/linker-bot/linkerbot-transport.git ~/linkerbot-deps/linkerbot-transport
git clone --branch main https://github.com/linker-bot/linkerbot-arm-python-sdk.git ~/linkerbot-deps/linkerbot-arm-python
python -m pip install -c "$ARM_CONSTRAINTS" -e "$HOME/linkerbot-deps/linkerbot-transport[can]"
python -m pip install -c "$ARM_CONSTRAINTS" -e "$HOME/linkerbot-deps/linkerbot-arm-python"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

## 5. Build the ROS2 Package

```bash
cd ~/linkerbot_ws
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
head -n 1 install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
python -c "import sys; print(sys.executable)"
source install/setup.bash
python "$(command -v ros2)" pkg prefix linker_arm_ros2
```

The generated node's first line should point to the current venv. Activating a venv does not change `/usr/bin/colcon`'s interpreter, so invoke that entry point with the current `python`. Building does not install the SDK for you.

## Using a New Terminal

```bash
ARM_ROS_DISTRO=humble  # Same distribution as during installation
source "/opt/ros/${ARM_ROS_DISTRO}/setup.bash"
source "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}/bin/activate"
source ~/linkerbot_ws/install/setup.bash
```

Continue with [Connecting and Starting](getting_started.md). If the wrong SDK loads, see [Troubleshooting](troubleshooting.md#sdk-source).

[Back to overview](environment_setup.md)
