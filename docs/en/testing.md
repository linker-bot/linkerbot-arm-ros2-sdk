# Testing and Docker Validation

## Environment Check

Install the latest SDK and Transport from `main` using the [installation instructions](INSTALLATION.md), then run inside the ROS venv:

```bash
ARM_ROS_SOURCE="$HOME/linkerbot_ws/src/linkerbot-arm-ros2"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

The check imports real ROS modules, reports numerical-library and SDK origins, verifies cancellable homing and feedback capabilities, and computes finite FK with all six left/right A7, A7 Lite, and P7 URDFs. It does not construct arm instances or open CAN.

## Local Regression Tests

```bash
cd "$ARM_ROS_SOURCE"
ARM_CONSTRAINTS=$(python scripts/check_ros_environment.py --print-constraints)
python -m pip install -c "$ARM_CONSTRAINTS" -e '.[test]'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_timeout tests
```

Only `tests/` is collected by default; the physical lifecycle tool is not run. Some tests skip when ROS2 is missing, which is not a passing ROS2 integration result. The timeout plugin is explicitly enabled to avoid interference from unrelated system pytest plugins.

## Docker Validation

The host needs access to the Docker daemon. Image building needs APT/PyPI network access, but repository credentials are not copied into the image. Run from the ROS2 checkout; the example dependency directories must not already exist:

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
mkdir -p ../arm-docker-deps
git clone --branch main https://github.com/linker-bot/linkerbot-arm-python-sdk.git ../arm-docker-deps/sdk
git clone --branch main https://github.com/linker-bot/linkerbot-transport.git ../arm-docker-deps/transport
bash docker/verify.sh humble ../arm-docker-deps/sdk ../arm-docker-deps/transport
bash docker/verify.sh jazzy ../arm-docker-deps/sdk ../arm-docker-deps/transport
```

Test containers use no network, device passthrough, or published ports. Results default to `docker/results/<distribution>/`; the fourth argument selects another directory. They include source commits and changes, build/test logs, JUnit XML, and colcon results. Failures return a nonzero exit code. Temporary containers and build contexts are removed automatically; images are retained.

Set `ARM_DOCKER_NO_CACHE=1` before the command when APT layers need refreshing. The SDK and Transport commits in the logs record the sources actually used for the test.

## Scope of Validation

Checks cover Python/ROS compatibility, dependencies, all six URDF FKs, colcon build, node interpreter, package discovery, both launch descriptions, and ROS2/SDK tests without hardware. Integration regressions use real ROS2 → adapter → A7 SDK → transport, replacing only the CAN driver, to check send failures, feedback age, asynchronous configuration, stop cancellation, and target ordering.

APT packages, image tags, and the SDK and Transport `main` branches may change. Use the actual logs when rerunning.

Real CAN communication, motion, stopping distance, and calibration require separate physical-device validation. Other CPU architectures require validation on that platform.

[Back to overview](environment_setup.md)
