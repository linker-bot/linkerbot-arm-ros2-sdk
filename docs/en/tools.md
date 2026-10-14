# Calibration and Diagnostic Tools

Run these tools from the ROS2 checkout with the [paired Python environment](INSTALLATION.md) activated. Use only one controller per device. Stop the arm node and other controllers before running detection, calibration, or SDK lifecycle tools against that arm.

<a id="can-detection"></a>

## CAN Interface Detection

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
g++ scripts/detect_can.cpp -std=c++17 -o scripts/detect_can
sudo scripts/detect_can
cat scripts/can_config.yaml
```

The detector enumerates interfaces, attempts to bring inactive interfaces up at 1 Mbit/s, and actively probes devices. It writes `can_config.yaml` beside the executable. It does not change `config/arm_config.yaml`; verify the results, manually copy the left/right interface names, and rebuild.

## ROS2 Zero Service

The node supports the zero-calibration service for A7, A7 Lite, and P7. After confirming that the arm is disabled and physically at zero, call [calibrate_zero](services.md#zero-calibration). This service stores zero without the standalone tool's interactive confirmation or reconnection verification.

<a id="zero-calibration"></a>

## Standalone Zero Calibration

`scripts/calibrate_arm_zero.py` supports only **A7 / A7 Lite**. It connects using the configuration, confirms physical zero, writes calibration, reconnects, and verifies slow-speed homing. Start with one arm at a time:

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
python scripts/calibrate_arm_zero.py --side left --config config/arm_config.yaml
# List all options without connecting an arm
python scripts/calibrate_arm_zero.py --help
```

| Common option | Default | Meaning |
| --- | --- | --- |
| `--side` | `both` | `left`, `right`, or `both` |
| `--home-velocity` | `0.3` | Homing verification speed, rad/s |
| `--tolerance` | `0.05` | Allowed absolute homing error per joint, rad |
| `--disable-only` | Off | Connect and disable only; do not calibrate or home |

The tool queries the current ROS domain's node graph and rejects calibration if default arm nodes are present or the query fails. This snapshot is not an exclusive device lock; it cannot detect arbitrary node names, other domains, or standalone SDK processes. The operator must stop every process that could control the device.

If a workspace `task_config.json` specifies a different model, the tool rejects the operation; correct the configuration first. Use `--ignore-config-mismatch` only after manually confirming that YAML matches the device. On exit, the tool attempts to disable and close the device and logs cleanup errors.

## Standalone SDK Lifecycle Check

Supports only **A7 / A7 Lite** and helps separate SDK communication failures from ROS2 integration issues:

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
python scripts/test_lifecycle.py --single left --arm-type a7lite --left-can can0
```

This tool enables, homes, and sends streamed targets: **it causes physical motion** and is not a unit test without hardware. SIGINT/SIGTERM requests homing cancellation, followed by attempts to disable and close each arm. For tests without hardware, see [Testing and Docker Validation](testing.md).

[Back to overview](environment_setup.md)
