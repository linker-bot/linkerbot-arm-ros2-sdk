"""Real ROS service -> SDK -> transport regressions with a fake physical driver."""

import struct
import threading
import time
from types import SimpleNamespace

import can
import pytest

pytest.importorskip("rclpy")
import rclpy
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

from linker_arm_ros2 import arm_node
from linker_arm_ros2.sdk_adapter import LinkerBotSDKAdapter

# arm_node must bootstrap source SDK discovery before importing SDK classes.
# isort: split
from linkerbot_arm._transport import can as sdk_can
from linkerbot_arm.arm.a7.a7 import A7
from linkerbot_arm.arm.a7.motor import A7Motor, SensorType
from linkerbot_arm.motion_timer import MotionTimer
from linkerbot_transport.can import CANTransport


class FakeDriver:
    """Inject failures only at the physical send boundary; never open a bus."""

    def __init__(self):
        self.callbacks = []
        self.failed = []
        self.sent = []
        self.failure = None

    def subscribe(self, callback):
        self.callbacks.append(callback)

    def unsubscribe(self, callback):
        self.callbacks.remove(callback)

    def send_now(self, message):
        if (message.arbitration_id, bytes(message.data[:1])) == self.failure:
            self.failed.append(message)
            raise OSError("injected physical CAN send failure")
        self.sent.append(message)

    def feed(self, message):
        for callback in tuple(self.callbacks):
            callback(message)

    def stop(self):
        self.callbacks.clear()


@pytest.fixture(autouse=True)
def forbid_hardware(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Transport integration tests must not open CAN hardware")

    monkeypatch.setattr(can, "Bus", forbidden)
    monkeypatch.setattr(can.interface, "Bus", forbidden)


@pytest.fixture
def ros_node(monkeypatch, wait_for_tasks):
    driver = FakeDriver()

    def transport(name, backend, **kwargs):
        return CANTransport(
            name, backend, dispatcher_factory=lambda on_error: driver, **kwargs
        )

    monkeypatch.setattr(sdk_can, "CANTransport", transport)
    connection = sdk_can.ManagedCANDispatcher("regression", "virtual", "a7", "left")
    # Skip discovery/kinematics construction, retain the actual SDK public
    # methods, motor encoders, receipt waits, transport scheduler and RX route.
    raw = A7.__new__(A7)
    raw._can_dispatcher = connection
    raw._motors = [A7Motor(mid, connection) for mid in range(61, 68)]
    raw._motion_timer = MotionTimer()
    raw._closed = False
    raw._closing = False
    raw._polling = False
    raw._resources_closed = False
    raw._bus_error = None
    raw._kx = SimpleNamespace(get_joint_limits=lambda: [(-3.0, 3.0)] * 7)
    for motor in raw._motors:
        motor._enabled = True
    adapter = LinkerBotSDKAdapter.__new__(LinkerBotSDKAdapter)
    adapter._arm = raw
    adapter._arm_type = "a7"
    monkeypatch.setattr(arm_node, "create_arm", lambda **kwargs: adapter)
    rclpy.init(args=["--ros-args", "-p", "auto_enable:=false"])
    node = None
    try:
        node = arm_node.ArmNode()
        node.enabled = True
        node._may_be_enabled = True
        node.wait_for_tasks = lambda: wait_for_tasks(node)
        yield node, raw, connection, driver
    finally:
        driver.failure = None
        try:
            if node is not None:
                node.destroy_node()
        finally:
            connection.stop()
            if rclpy.ok():
                rclpy.shutdown()


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.002)
    assert predicate(), "integration worker did not reach the expected state"


def drain(connection):
    wait_until(
        lambda: (
            connection._tx.get_health().pending_fifo == 0
            and connection._tx.get_health().in_flight_frames == 0
        )
    )


def call_service(node, name):
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    client = node.create_client(Trigger, "/arm_node/" + name)
    try:
        assert client.wait_for_service(timeout_sec=2)
        future = client.call_async(Trigger.Request())
        deadline = time.monotonic() + 3
        while not future.done() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.01)
        assert future.done()
        return future.result()
    finally:
        node.destroy_client(client)
        executor.remove_node(node)
        executor.shutdown()


def command(node, value):
    msg = JointState()
    msg.position = [float(value)] * 7
    node._cmd_callback(msg)
    node.wait_for_tasks()


@pytest.mark.parametrize("window", [1, 3])
def test_new_target_supersedes_pending_before_physical_send(
    ros_node, hold_speed_finalization, window
):
    node, raw, connection, driver = ros_node
    node.filter_window = window
    finished, release = hold_speed_finalization(node)
    first = JointState()
    first.position = [0.2] * 7
    node._cmd_callback(first)
    assert finished.wait(2)
    assert node._tasks.configuring_speed
    pending = JointState()
    pending.position = [0.4] * 7
    node._cmd_callback(pending)
    release.set()
    node.wait_for_tasks()

    command(node, 0.6)
    node._control_loop()
    drain(connection)
    targets = [frame for frame in driver.sent if bytes(frame.data[:1]) == b"\x0a"]
    assert len(targets) == 14
    assert [frame.arbitration_id for frame in targets] == list(range(61, 68)) * 2
    expected = 0.6 if window == 1 else 0.4
    values = [struct.unpack("<f", bytes(frame.data[1:5]))[0] for frame in targets]
    assert values == pytest.approx([0.2] * 7 + [expected] * 7)
    assert [motor.control_angle.angle for motor in raw._motors] == pytest.approx(
        [expected] * 7
    )
    assert node._pending_command is None


def test_home_physical_speed_failure_requires_complete_retry(ros_node):
    node, raw, connection, driver = ros_node
    command(node, 0.1)
    assert node._set_speed_mode(normal=True)
    drain(connection)
    driver.failure = (63, b"\x1f")
    receipt = connection._last_target_receipt
    response = call_service(node, "home")
    assert not response.success
    assert "injected physical CAN send failure" in response.message
    assert [motor.control_velocity.velocity for motor in raw._motors] == [
        0.5,
        0.5,
        3.0,
        3.0,
        3.0,
        3.0,
        3.0,
    ]
    assert node._speed_recovery_pending and not node._slow_speed_ready
    assert node.enabled and not node._halted
    command(node, 0.4)
    assert connection._last_target_receipt is receipt
    assert node._speed_recovery_pending
    drain(connection)
    driver.sent.clear()
    driver.failure = None
    command(node, 0.8)
    drain(connection)
    assert connection._last_target_receipt is not receipt
    assert len(driver.sent) == 14
    for mid, message in zip(range(61, 68), driver.sent[:7]):
        assert message.arbitration_id == mid
        assert bytes(message.data) == b"\x1f" + struct.pack("<f", 0.5)
    for mid, message in zip(range(61, 68), driver.sent[7:]):
        assert message.arbitration_id == mid
        assert bytes(message.data) == b"\x0a" + struct.pack("<f", 0.8)
    assert not node._speed_recovery_pending and not node.normal_speed_active
    assert [motor.control_velocity.velocity for motor in raw._motors] == [0.5] * 7


def test_disable_reports_physical_failure_and_preserves_uncertain_state(ros_node):
    node, raw, connection, driver = ros_node
    driver.failure = (63, b"\x2a")
    response = call_service(node, "disable")
    drain(connection)
    assert not response.success
    assert "injected physical CAN send failure" in response.message
    assert len(driver.failed) == 1
    assert bytes(driver.failed[0].data) == b"\x2a\x00"
    assert len(driver.sent) == 6
    assert connection._error is None
    assert node.enabled and node._may_be_enabled and node._halted
    assert raw._motors[2].enabled
    assert all(not motor.enabled for i, motor in enumerate(raw._motors) if i != 2)
    driver.failure = None
    response = call_service(node, "disable")
    assert response.success
    assert not node.enabled and not node._may_be_enabled


def test_old_queued_feedback_is_suppressed(ros_node):
    node, raw, connection, driver = ros_node
    blocked = threading.Event()
    release = threading.Event()
    first = True

    def block_receiver(message):
        nonlocal first
        if first:
            first = False
            blocked.set()
            assert release.wait(3)

    with connection._lock:
        connection._callbacks.insert(0, block_receiver)
    published = []
    node.state_pub.publish = published.append
    node._publish_state()
    try:
        driver.feed(
            can.Message(arbitration_id=61, is_extended_id=False, data=[0x01, 1])
        )
        assert blocked.wait(2)
        for mid in range(61, 68):
            for cmd in (SensorType.POSITION, SensorType.VELOCITY, SensorType.TORQUE):
                driver.feed(
                    can.Message(
                        arbitration_id=mid,
                        is_extended_id=False,
                        data=bytes([cmd]) + struct.pack("<f", 0.25),
                    )
                )
        last_rx = connection._transport.get_health().last_successful_rx_s
        time.sleep(0.65)
        assert time.monotonic() - last_rx > node.feedback_timeout
        release.set()
        wait_until(
            lambda: all(
                joint.torque_received_at is not None
                for joint in raw.get_feedback().joints
            )
        )
        assert raw.get_feedback().oldest_received_at <= last_rx
        assert not raw.get_feedback().is_fresh(node.feedback_timeout)
        node._publish_state()
        assert published == []
    finally:
        release.set()
