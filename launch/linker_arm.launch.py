#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('linker_arm_ros2'),
        'config',
        'linker_arm.yaml',
    )

    return LaunchDescription([
        Node(
            package='linker_arm_ros2',
            executable='linker_arm_node',
            name='linker_arm_node',
            output='screen',
            parameters=[config],
        ),
    ])
