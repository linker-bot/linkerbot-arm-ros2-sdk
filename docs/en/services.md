# Lifecycle Services

All services use `std_srvs/srv/Trigger`. Launch names the left node `left_arm_node` and the right node `right_arm_node`. Services are private node names. Direct node execution defaults to `/arm_node/<service>`; namespaces or node renaming change the full path.

## Service List

| Suffix | Behavior |
| --- | --- |
| `enable` | Disable, enable, apply A7 Lite KP, and home at slow speed |
| `disable` | Cancel the active task, disable, and pause target admission |
| `home` | Perform cancellable slow-speed homing while enabled |
| `emergency_stop` | Cancel the active task, invoke SDK software stop, and pause target admission |
| `reset_error` | Reset motor errors without automatically resuming control |
| `calibrate_zero` | Store the current pose as zero while disabled |

`home` moves to the calibrated zero pose; `calibrate_zero` stores the current pose as zero. They are not interchangeable.

## Calling Services

```bash
ros2 service call /left_arm_node/enable std_srvs/srv/Trigger '{}'
ros2 service call /left_arm_node/home std_srvs/srv/Trigger '{}'
ros2 service call /left_arm_node/reset_error std_srvs/srv/Trigger '{}'
```

Replace `left_arm_node` with `right_arm_node` for the right arm. `success: true` means the operation returned, not merely that it was queued. On `success: false`, read the reason in `message`.

Enable/configuration operations check physical send receipts, which do not confirm motor execution. Homing return semantics depend on the SDK implementation; verify arrival through feedback and the physical device.

## Busy States and Failures

Lifecycle work runs in a worker while the service coroutine waits for its result. State publication can continue. Only one ordinary task is admitted at a time; other ordinary services fail while busy rather than queueing. Speed configuration uses the same worker.

`disable` and `emergency_stop` can cancel the active task. The cancelled request fails. A stop response also waits for SDK calls and the original worker to exit; software stop is not an instantaneous hardware emergency stop.

Startup or enable failure triggers an attempt to disable and close the SDK. Restart the node after the connection closes. Partial speed-configuration failure during homing preserves the SDK error and requires all joints to recover slow speed before further targets. For other homing failures, inspect logs, feedback, and device state before retrying.

<a id="stop-and-resume"></a>

## Stopping and Resuming

```bash
ros2 service call /left_arm_node/emergency_stop std_srvs/srv/Trigger '{}'
ros2 service call /left_arm_node/disable std_srvs/srv/Trigger '{}'
```

Stopping clears pending targets. Late speed receipts do not restore motion state. Streaming resumes after a successful explicit `enable`, or a successful `home` while still enabled. `reset_error` alone does not resume it.

After `disable`, call `enable`, since `home` requires the arm to be enabled. The A7 Lite SDK also latches its stop state rather than recovering automatically after two seconds.

<a id="zero-calibration"></a>

## Zero Calibration

Only after confirming that the arm is disabled and physically at zero, call:

```bash
ros2 service call /left_arm_node/calibrate_zero std_srvs/srv/Trigger '{}'
```

The node rejects calibration while enabled or possibly partially enabled. For interactive confirmation, reconnection, and homing verification, use the [standalone calibration tool](tools.md#zero-calibration), which supports only A7 and A7 Lite.

[Back to overview](environment_setup.md)
