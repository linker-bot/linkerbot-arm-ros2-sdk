# Updating Sources

Stop the arm node and other controllers before updating. Preserve uncommitted local changes. This example assumes that the ROS2 checkout is on `main` and can fast-forward. Resolve divergence or local conflicts first rather than using a forced reset.

## Update ROS2 and Dependencies

```bash
ARM_ROS_SOURCE="$HOME/linkerbot_ws/src/linkerbot-arm-ros2"
git -C "$ARM_ROS_SOURCE" remote set-url origin https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2.git
git -C "$ARM_ROS_SOURCE" status --short --branch
git -C "$ARM_ROS_SOURCE" pull --ff-only origin main

ARM_ROS_DISTRO=humble  # Same as the installed environment
source "/opt/ros/${ARM_ROS_DISTRO}/setup.bash"
source "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}/bin/activate"
ARM_CONSTRAINTS=$(python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py" --print-constraints)
python -m pip install --force-reinstall -c "$ARM_CONSTRAINTS" \
  -r "$ARM_ROS_SOURCE/requirements/source-versions.txt"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
cd ~/linkerbot_ws
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
```

Update the SDK according to the ROS2 manifest rather than substituting any package with the same version. Transport is reinstalled from current `main` without a version, tag, or SHA installation constraint. For HTTPS editable installs, update transport `main` and the manifest-selected SDK checkout, then reinstall using the [installation instructions](INSTALLATION.md#paired-sdk).

## Changing Distributions

Create a new venv and workspace for Humble or Jazzy using [Installation and Build](INSTALLATION.md). Do not reuse build results from the other distribution. After updating, verify the actual SDK origin, node interpreter, and configuration before [starting the device](getting_started.md).

[Back to overview](environment_setup.md)
