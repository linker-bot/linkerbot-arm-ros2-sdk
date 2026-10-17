# Arm ROS2 User Manual

`linker_arm_ros2` connects the arm Python SDK to ROS2 through seven-joint target topics, joint-state topics, and lifecycle services. It supports left and right A7, A7 Lite, and P7 arms.

## Quick Start

[Installation and Build](INSTALLATION.md): choose Humble or Jazzy, install the latest SDK and Transport from `main`, and build the ROS2 package. Then connect the device and choose its model guide.

Before starting, confirm the model, side, and CAN interface. The repository defaults to `auto_enable: true`, which enables and homes the arm at slow speed. The [first-session example](getting_started.md) disables automatic enabling and starts motion through a service.

### Supported Environments

| Operating system | ROS2 | Python |
| --- | --- | --- |
| Ubuntu 22.04 | Humble | 3.10 |
| Ubuntu 24.04 | Jazzy | 3.12 |

Both use the same node and configuration. Use separate virtual environments and build workspaces. Other systems and CPU architectures require separate validation.

## Connecting Devices

- [Connecting and Starting](getting_started.md): configure CAN, start one or both arms, and read the first state message.
- [Configuration](configuration.md): model, interface, speeds, filtering, and feedback timeout.

<a id="models"></a>

## Device Features

Choose the model and expand its configuration, control, feedback, stopping, and model differences. The same guides apply to Humble and Jazzy.

| Model | Feature Guide |
| --- | --- |
| [A7](tutorials/a7.md) | V1 motor PP position control, left/right targets, and feedback |
| [A7 Lite](tutorials/a7lite.md) | PP control and position KP, with MIT / CSP interface limits |
| [P7](tutorials/p7.md) | Mixed V1 / V2 joints, continuous targets, and host-side limits |

Model guides refer to these shared interface references:

- [Topics and Joint Control](topics.md): target format, named joints, speed transitions, and filtering.
- [Lifecycle Services](services.md): enable, disable, home, software stop, reset errors, and calibrate zero.
- [Feedback Validity](feedback.md): publication pauses, recovery, and `header.stamp` semantics.

ROS2 does not yet support H75 or expose all SDK control modes or Cartesian kinematics interfaces.

## Further Information

- [Calibration and Diagnostic Tools](tools.md): CAN detection, zero calibration, and SDK lifecycle checks.
- [Testing and Docker Validation](testing.md): checks without hardware, Humble/Jazzy tests, and validation limits.
- [Troubleshooting](troubleshooting.md): installation, startup, data, and control problems.
- [Updating Sources](sdk_update.md): update ROS2, SDK, and Transport from `main`.

### Project Names

| Component | Name |
| --- | --- |
| ROS2 source repository | [linkerbot-arm-ros2-sdk](https://github.com/linker-bot/linkerbot-arm-ros2-sdk) |
| ROS2 package / Python import | `linker_arm_ros2` |
| SDK source repository | [linkerbot-arm-python-sdk](https://github.com/linker-bot/linkerbot-arm-python-sdk) |
| SDK distribution / Python import | `linkerbot-arm` / `linkerbot_arm` |
| Communication dependency | [linkerbot-transport](https://github.com/linker-bot/linkerbot-transport) |

Only the standalone arm SDK and transport are required. The hand SDK and the old aggregate SDK are unnecessary.
