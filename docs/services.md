# 生命周期服务

所有服务使用 `std_srvs/srv/Trigger`。左臂 launch 的节点名为 `left_arm_node`，右臂为 `right_arm_node`；服务是节点私有名称，直接运行节点默认路径为 `/arm_node/<服务>`，namespace 或重命名节点会改变完整路径。

## 服务列表

| 服务后缀 | 行为 |
| --- | --- |
| `enable` | 先失能，再使能、应用 A7 Lite KP 并慢速回零 |
| `disable` | 取消活动任务，失能并暂停目标接收 |
| `home` | 已使能时执行可取消的慢速回零 |
| `emergency_stop` | 取消活动任务，调用 SDK 软件停止并暂停目标接收 |
| `reset_error` | 重置电机错误，不自动恢复控制 |
| `calibrate_zero` | 失能后把当前位置写成零位 |

`home` 是移动到已标定零位，`calibrate_zero` 是保存当前位置为零位，二者不能互换。

## 调用示例

```bash
ros2 service call /left_arm_node/enable std_srvs/srv/Trigger '{}'
ros2 service call /left_arm_node/home std_srvs/srv/Trigger '{}'
ros2 service call /left_arm_node/reset_error std_srvs/srv/Trigger '{}'
```

右臂将 `left_arm_node` 替换为 `right_arm_node`。`success: true` 表示操作已返回，不是刚进入后台队列；`success: false` 时读取 `message` 中的原因。

使能/配置操作会检查物理发送回执，但回执不代表电机已经执行。回零的返回语义由 SDK 实现决定；到位状态须通过反馈及实机确认。

## 忙碌与失败

生命周期工作在后台执行，服务协程等待结果，状态发布仍可继续。普通任务同时只接受一个；忙碌时其他普通服务返回失败，不排队。速度配置也占用同一个 worker。

`disable` / `emergency_stop` 可以取消当前任务。被取消请求返回失败；停止请求还需等待 SDK 调用及原 worker 退出，软件停止并非无延迟的硬件急停。

启动或使能失败会尝试失能并关闭 SDK，连接关闭后应重启节点。回零速度配置部分失败时保留 SDK 错误；后续目标须先恢复全臂慢速。回零其他失败须检查日志、反馈及设备状态后再决定是否重试。

<a id="stop-and-resume"></a>

## 停止与恢复

```bash
ros2 service call /left_arm_node/emergency_stop std_srvs/srv/Trigger '{}'
ros2 service call /left_arm_node/disable std_srvs/srv/Trigger '{}'
```

停止会清除待发目标。迟到的速度配置回执不会恢复节点运动状态。停止后显式 `enable` 成功，或仍使能时 `home` 成功，才重新开放流式控制；单独 `reset_error` 不恢复。

`disable` 后需调用 `enable`，因为 `home` 要求已使能。A7 Lite SDK 的停止也持续锁存，不会等待两秒自动恢复。

<a id="zero-calibration"></a>

## 零位标定

确认设备失能且处于物理零位后，才调用：

```bash
ros2 service call /left_arm_node/calibrate_zero std_srvs/srv/Trigger '{}'
```

节点处于使能或可能部分使能状态时拒绝标定。需要交互确认、重连和回零验证时，使用[独立标定工具](tools.md#zero-calibration)；该工具只支持 A7 / A7 Lite。

[返回总览](environment_setup.md)
