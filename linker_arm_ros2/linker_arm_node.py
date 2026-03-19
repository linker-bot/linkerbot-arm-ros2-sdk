#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROS2 node for controlling LinkerBot robotic arms via linkerbot-python-sdk.

Publishes joint states and subscribes to joint commands,
bridging ROS2 communication with the linkerbot-python-sdk API.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray


class LinkerArmNode(Node):
    def __init__(self):
        super().__init__('linker_arm_node')

        self.declare_parameter('publish_rate', 100.0)
        self.declare_parameter('can_interface', 'can0')

        publish_rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        self.can_interface = self.get_parameter('can_interface').get_parameter_value().string_value

        self.joint_state_pub = self.create_publisher(
            JointState, 'linker_arm/joint_states', 10)

        self.joint_cmd_sub = self.create_subscription(
            Float64MultiArray, 'linker_arm/joint_commands',
            self.joint_cmd_callback, 10)

        self.timer = self.create_timer(1.0 / publish_rate, self.timer_callback)

        self.get_logger().info(
            f'LinkerArmNode started on CAN interface: {self.can_interface}')

    def timer_callback(self):
        # TODO: Read joint states from linkerbot-python-sdk and publish
        pass

    def joint_cmd_callback(self, msg: Float64MultiArray):
        # TODO: Send joint commands via linkerbot-python-sdk
        self.get_logger().debug(f'Received joint command: {msg.data}')


def main(args=None):
    rclpy.init(args=args)
    node = LinkerArmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
