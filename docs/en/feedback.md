# Feedback Validity and Timestamps

The node reads the SDK's immutable local `get_feedback()` snapshot without sending queries or computing forward kinematics. JointState is published only when position, velocity, and torque are valid and fresh for all seven joints.

## Pausing and Recovering

Any of the following pauses state publication for the current cycle:

- The SDK is closed or reports a CAN fault.
- Any field is missing, NaN/Inf, has a future reception time, or exceeds `feedback_timeout` in reception age.
- Feedback has not yet been mapped into the current ROS clock epoch.

The node logs pause reasons and recovery when the state changes. It does not fill missing data with zeros, NaN messages, or current timestamps. Subscribers should treat an interrupted topic as unavailable data rather than indefinitely treating the last message as current state.

Feedback timeout uses the host monotonic clock, unaffected by system clock changes or paused ROS simulation time. The default 0.5-second limit should exceed the slowest field's polling/heartbeat period plus scheduling margin; examples include A7's default 50 ms torque polling and P7's last two motors' 200 ms heartbeats.

A feedback pause **does not itself send stop or disable commands**. Applications that stop on feedback loss must implement that behavior and call [Lifecycle Services](services.md). After SDK closure or a bus fault, rebuild the connection or restart the node according to lifecycle rules; motion does not resume automatically.

## What `header.stamp` Means

A message may combine fields received at different times. The node uses the **oldest host reception time across every joint and published field**, then chooses the latest observed ROS timestamp no later than that reception.

- Repeated caches retain the same timestamp; publication at 100 Hz does not imply new measurements at 100 Hz.
- Normally, rounding backward adds at most one publication callback interval; scheduling delays can increase this error.
- At startup, all fields must update after the first clock observation. Initialization caches are not labelled as current data.

The SDK preserves the original host reception time passed from the transport reception/dispatch entry point instead of relabelling queued feedback with its later decode time. This is still not an embedded sampling timestamp and cannot measure firmware or driver buffering before that recording point.

## Simulation Time and Clock Changes

With `use_sim_time`, timestamps use observed `/clock` values rather than subtracting host age from simulation time. Paused simulation time can retain identical stamps while host age still expires. When the ROS timer pauses, it also stops publishing.

A publication callback clears the mapping when it observes ROS time moving backward, a clock-mode change, or a difference exceeding 100 ms between system-time and monotonic-time increments. All fields must then update again. Forward simulation-time jumps retain the old mapping; older samples keep their pre-jump stamps. Changes not observed between callbacks cannot be fully tracked.

These timestamps conservatively express data age; they do not guarantee synchronized sampling across devices.

[Back to overview](environment_setup.md)
