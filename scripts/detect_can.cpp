// CAN设备自动检测程序
// 支持检测: 
//   - 左右灵巧手 (三种协议: Type1/Type2/Type3)
//   - Linker TA 遥操作手臂
//   - A7Lite 机械臂 (全7关节检测)
//   - A7 机械臂 (全7关节检测)
// 
// 优化策略:
//   - 第一阶段: 快速检测设备类型 (只检测单关节)
//   - 第二阶段: 只对机械臂进行全关节检测 (唤醒所有电机)
// 
// 编译: g++ detect_can.cpp -std=c++17 -o detect_can

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <ifaddrs.h>
#include <filesystem>
#include <thread>
#include <chrono>

namespace fs = std::filesystem;

// ============================================================================
// 固定参数
// ============================================================================
static constexpr int WARMUP_MS = 2000;       // CAN 接口启动后预热时间 (毫秒)
static constexpr int JOINT_DELAY_MS = 50;    // 每关节检测间延时 (毫秒)

static constexpr timeval RX_TIMEOUT{0, 100000}; // 100 ms

// ============================================================================
// 设备类型枚举
// ============================================================================
enum class DeviceType {
    UNKNOWN,
    HAND,           // 灵巧手
    TA_ARM,         // TA 遥操作手臂
    A7LITE_ARM,  // A7Lite 机械臂
    A7_ARM        // A7 机械臂
};

const char* device_type_name(DeviceType t) {
    switch (t) {
        case DeviceType::HAND: return "灵巧手";
        case DeviceType::TA_ARM: return "TA 遥操臂";
        case DeviceType::A7LITE_ARM: return "A7Lite 机械臂";
        case DeviceType::A7_ARM: return "A7 机械臂";
        default: return "未知";
    }
}

struct Job {
    const char* name;
    const char* desc;
    uint32_t id;
    bool is_ext;
    uint8_t data0;
    uint8_t dlc;
    uint8_t data[8];
    DeviceType dev_type;
    int joint_index;  // 1-7, 0=非关节
};

// ============================================================================
// 响应检查函数
// ============================================================================
static bool check_a7lite_response(uint32_t tx_id, uint32_t rx_id) {
    static const uint32_t left_tx[] = {0x8000FD3D, 0x8000FD3E, 0x8000FD3F, 0x8000FD40, 0x8000FD41, 0x8000FD42, 0x8000FD43};
    static const uint32_t left_rx[] = {0x80003DFE, 0x80003EFE, 0x80003FFE, 0x800040FE, 0x800041FE, 0x800042FE, 0x800043FE};
    static const uint32_t right_tx[] = {0x8000FD33, 0x8000FD34, 0x8000FD35, 0x8000FD36, 0x8000FD37, 0x8000FD38, 0x8000FD39};
    static const uint32_t right_rx[] = {0x800033FE, 0x800034FE, 0x800035FE, 0x800036FE, 0x800037FE, 0x800038FE, 0x800039FE};
    
    for (int i = 0; i < 7; i++) {
        if (tx_id == left_tx[i] && rx_id == left_rx[i]) return true;
        if (tx_id == right_tx[i] && rx_id == right_rx[i]) return true;
    }
    return false;
}

// ============================================================================
// CAN 通讯函数
// ============================================================================
bool ping_once(const std::string& ifname, const Job& job) {
    int sock = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (sock < 0) return false;

    ifreq ifr{};
    strncpy(ifr.ifr_name, ifname.c_str(), IFNAMSIZ - 1);
    if (ioctl(sock, SIOCGIFINDEX, &ifr) < 0) {
        close(sock);
        return false;
    }

    sockaddr_can addr{};
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        close(sock);
        return false;
    }

    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &RX_TIMEOUT, sizeof(RX_TIMEOUT));

    can_frame tx{};
    tx.can_id = job.id | (job.is_ext ? CAN_EFF_FLAG : 0);
    
    if (job.dlc > 0) {
        tx.can_dlc = job.dlc;
        memcpy(tx.data, job.data, 8);
    } else {
        if (job.dev_type == DeviceType::HAND && (job.id == 0x27 || job.id == 0x28)) {
            tx.can_dlc = 1;
        } else {
            tx.can_dlc = 8;
        }
        memset(tx.data, 0, 8);
        tx.data[0] = job.data0;
    }

    if (write(sock, &tx, sizeof(tx)) != sizeof(tx)) {
        close(sock);
        return false;
    }

    can_frame rx{};
    for (int i = 0; i < 5; i++) {
        ssize_t n = read(sock, &rx, sizeof(rx));
        if (n > 0) {
            switch (job.dev_type) {
                case DeviceType::TA_ARM:
                    if (tx.can_id == 0x64 && (rx.can_id == 0x64 || rx.can_id == 0x40000064)) {
                        close(sock);
                        return true;
                    }
                    break;
                case DeviceType::A7LITE_ARM:
                    if (check_a7lite_response(tx.can_id, rx.can_id)) {
                        close(sock);
                        return true;
                    }
                    break;
                case DeviceType::A7_ARM:
                    if (rx.can_id == job.id) {
                        close(sock);
                        return true;
                    }
                    break;
                case DeviceType::HAND:
                    if (job.dlc == 0 && rx.can_id == tx.can_id) {
                        close(sock);
                        return true;
                    }
                    if (job.dlc > 0 && job.data[0] == 0x01 && 
                        rx.can_id == tx.can_id && rx.data[0] == 0x01) {
                        close(sock);
                        return true;
                    }
                    break;
                default:
                    break;
            }
        }
    }
    
    close(sock);
    return false;
}

// ============================================================================
// 工具函数
// ============================================================================
static bool is_interface_up(const std::string& ifname) {
    int fd = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (fd < 0) return false;
    ifreq ifr{};
    strncpy(ifr.ifr_name, ifname.c_str(), IFNAMSIZ - 1);
    bool up = (ioctl(fd, SIOCGIFFLAGS, &ifr) == 0) && (ifr.ifr_flags & IFF_UP);
    close(fd);
    return up;
}

std::vector<std::string> detect_can_devices() {
    std::vector<std::string> cans;
    ifaddrs *ifa = nullptr;
    if (getifaddrs(&ifa) == -1) return cans;
    for (ifaddrs *p = ifa; p; p = p->ifa_next) {
        if (!p->ifa_name) continue;
        std::string name(p->ifa_name);
        if (name.rfind("can", 0) == 0 && name.length() <= 5) {
            cans.emplace_back(name);
        }
    }
    freeifaddrs(ifa);
    return cans;
}

// ============================================================================
// 主函数
// ============================================================================
int main(int /*argc*/, char* argv[]) {
    printf("============================================================\n");
    printf("CAN 设备自动检测程序\n");
    printf("============================================================\n");
    
    std::vector<std::string> buses = detect_can_devices();
    if (buses.empty()) {
        fprintf(stderr, "未检测到CAN接口\n");
        return 1;
    }

    printf("检测到 %zu 个CAN接口: ", buses.size());
    for (auto& b : buses) printf("%s ", b.c_str());
    printf("\n");

    // 启动 CAN 接口
    bool any_started = false;
    for (auto& b : buses) {
        if (!is_interface_up(b)) {
            system(std::string("ip link set " + b + " down 2>/dev/null").c_str());
            system(std::string("ip link set " + b + " up type can bitrate 1000000").c_str());
            system(std::string("chmod 0666 /sys/class/net/" + b + "/tx_queue_len 2>/dev/null").c_str());
            system(std::string("echo 1024 > /sys/class/net/" + b + "/tx_queue_len 2>/dev/null").c_str());
            usleep(100000);
            any_started = true;
        }
    }
    
    if (any_started) {
        printf("⏳ CAN 预热中 (%d ms)...\n", WARMUP_MS);
        std::this_thread::sleep_for(std::chrono::milliseconds(WARMUP_MS));
    }

    // ============================================================================
    // 第一阶段: 快速检测 (只检测单关节/单设备)
    // ============================================================================
    printf("\n【第一阶段】快速设备检测...\n");
    
    // 快速检测任务 (每种设备只检测一个代表)
    std::vector<Job> quick_jobs = {
        // 灵巧手
        {"left_hand",  "Linker Left Hand (Type1)",   0x28, false, 0x64, 0, {}, DeviceType::HAND, 0},
        {"right_hand", "Linker Right Hand (Type1)",  0x27, false, 0x64, 0, {}, DeviceType::HAND, 0},
        {"left_hand",  "Linker Left Hand (Type2)",   0x28, false, 0xC1, 0, {}, DeviceType::HAND, 0},
        {"right_hand", "Linker Right Hand (Type2)",  0x27, false, 0xC1, 0, {}, DeviceType::HAND, 0},
        {"left_hand",  "Linker Left Hand (Type3)",   0x28, false, 0x00, 7, {0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00}, DeviceType::HAND, 0},
        {"right_hand", "Linker Right Hand (Type3)",  0x27, false, 0x00, 7, {0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00}, DeviceType::HAND, 0},
        // TA 遥操臂
        {"ta_arm", "Linker TA Arm", 0x64, false, 0x00, 0, {}, DeviceType::TA_ARM, 0},
        // A7 机械臂 (只检测 J1)
        {"left_arm",  "A7 Left Arm",  0x3D, false, 0x00, 0, {}, DeviceType::A7_ARM, 1},
        {"right_arm", "A7 Right Arm", 0x33, false, 0x00, 0, {}, DeviceType::A7_ARM, 1},
        // A7Lite 机械臂 (只检测 J1)
        {"left_arm",  "A7Lite Left Arm",  0x8000FD3D, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 1},
        {"right_arm", "A7Lite Right Arm", 0x8000FD33, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 1},
    };
    
    std::map<std::string, std::string> hit;       // name -> bus
    std::map<std::string, std::string> hit_desc;  // name -> desc
    std::map<std::string, DeviceType> hit_type;   // name -> type
    std::map<std::string, int> arm_joint_count;   // "bus:arm_name" -> count
    
    for (auto& bus : buses) {
        for (auto& j : quick_jobs) {
            if (hit.find(j.name) != hit.end()) continue;
            
            if (ping_once(bus, j)) {
                printf("  %s: 发现 %s\n", bus.c_str(), j.desc);
                hit[j.name] = bus;
                hit_desc[j.name] = j.desc;
                hit_type[j.name] = j.dev_type;
                
                // 机械臂初始计数为1 (已检测到J1)
                if (j.dev_type == DeviceType::A7LITE_ARM || j.dev_type == DeviceType::A7_ARM) {
                    arm_joint_count[bus + ":" + j.name] = 1;
                }
            }
        }
    }

    // ============================================================================
    // 第二阶段: 机械臂全关节检测 (仅对发现的机械臂)
    // ============================================================================
    bool has_arm = false;
    for (auto& [name, type] : hit_type) {
        if (type == DeviceType::A7LITE_ARM || type == DeviceType::A7_ARM) {
            has_arm = true;
            break;
        }
    }
    
    if (has_arm) {
        printf("\n【第二阶段】机械臂全关节检测 (唤醒所有电机)...\n");
        
        for (auto& [name, type] : hit_type) {
            if (type != DeviceType::A7LITE_ARM && type != DeviceType::A7_ARM) {
                continue;
            }
            
            std::string bus = hit[name];
            bool is_left = (name == "left_arm");
            std::string key = bus + ":" + name;
            
            // 生成关节2-7的检测任务
            std::vector<Job> joint_jobs;
            
            if (type == DeviceType::A7LITE_ARM) {
                if (is_left) {
                    joint_jobs = {
                        {name.c_str(), "J2", 0x8000FD3E, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 2},
                        {name.c_str(), "J3", 0x8000FD3F, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 3},
                        {name.c_str(), "J4", 0x8000FD40, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 4},
                        {name.c_str(), "J5", 0x8000FD41, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 5},
                        {name.c_str(), "J6", 0x8000FD42, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 6},
                        {name.c_str(), "J7", 0x8000FD43, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 7},
                    };
                } else {
                    joint_jobs = {
                        {name.c_str(), "J2", 0x8000FD34, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 2},
                        {name.c_str(), "J3", 0x8000FD35, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 3},
                        {name.c_str(), "J4", 0x8000FD36, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 4},
                        {name.c_str(), "J5", 0x8000FD37, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 5},
                        {name.c_str(), "J6", 0x8000FD38, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 6},
                        {name.c_str(), "J7", 0x8000FD39, true, 0x00, 0, {}, DeviceType::A7LITE_ARM, 7},
                    };
                }
            } else if (type == DeviceType::A7_ARM) {
                if (is_left) {
                    joint_jobs = {
                        {name.c_str(), "J2", 0x3E, false, 0x00, 0, {}, DeviceType::A7_ARM, 2},
                        {name.c_str(), "J3", 0x3F, false, 0x00, 0, {}, DeviceType::A7_ARM, 3},
                        {name.c_str(), "J4", 0x40, false, 0x00, 0, {}, DeviceType::A7_ARM, 4},
                        {name.c_str(), "J5", 0x41, false, 0x00, 0, {}, DeviceType::A7_ARM, 5},
                        {name.c_str(), "J6", 0x42, false, 0x00, 0, {}, DeviceType::A7_ARM, 6},
                        {name.c_str(), "J7", 0x43, false, 0x00, 0, {}, DeviceType::A7_ARM, 7},
                    };
                } else {
                    joint_jobs = {
                        {name.c_str(), "J2", 0x34, false, 0x00, 0, {}, DeviceType::A7_ARM, 2},
                        {name.c_str(), "J3", 0x35, false, 0x00, 0, {}, DeviceType::A7_ARM, 3},
                        {name.c_str(), "J4", 0x36, false, 0x00, 0, {}, DeviceType::A7_ARM, 4},
                        {name.c_str(), "J5", 0x37, false, 0x00, 0, {}, DeviceType::A7_ARM, 5},
                        {name.c_str(), "J6", 0x38, false, 0x00, 0, {}, DeviceType::A7_ARM, 6},
                        {name.c_str(), "J7", 0x39, false, 0x00, 0, {}, DeviceType::A7_ARM, 7},
                    };
                }
            }
            
            // 检测剩余关节
            for (auto& jj : joint_jobs) {
                if (ping_once(bus, jj)) {
                    arm_joint_count[key]++;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(JOINT_DELAY_MS));
            }
            
            int count = arm_joint_count[key];
            const char* status = (count == 7) ? "✓" : "⚠";
            printf("  %s %s: %d/7 关节响应\n", status, hit_desc[name].c_str(), count);
        }
    }

    // ============================================================================
    // 警告信息
    // ============================================================================
    bool has_issues = false;
    for (auto& [key, count] : arm_joint_count) {
        if (count < 7) { has_issues = true; break; }
    }
    if (has_issues) {
        printf("\n⚠️  部分机械臂关节未响应，请检查电源和CAN连接\n");
    }

    // ============================================================================
    // 保存配置
    // ============================================================================
    if (hit.empty()) {
        fprintf(stderr, "\n⚠️  警告: 未检测到任何设备\n");
    }

    fs::path scriptDir = fs::path(argv[0]).parent_path();
    if (scriptDir.empty()) scriptDir = ".";
    fs::path yamlPath = scriptDir / "can_config.yaml";

    std::ofstream yaml(yamlPath);
    yaml << "# CAN设备配置文件\n";
    yaml << "# 自动生成，请勿手动编辑\n";
    yaml << "/**:\n";
    yaml << "  ros__parameters:\n";
    
    const char* keys[] = {"left_hand", "right_hand", "left_arm", "right_arm", "ta_arm"};
    for (const char* key : keys) {
        if (hit.find(key) != hit.end()) {
            yaml << "    " << key << ": \"" << hit[key] << "\" # " << hit_desc[key] << "\n";
        }
    }
    yaml.close();

    printf("\n============================================================\n");
    printf("检测结果:\n");
    for (const char* key : keys) {
        if (hit.find(key) != hit.end()) {
            printf("  %-10s: %s (%s)\n", key, hit[key].c_str(), hit_desc[key].c_str());
        }
    }
    printf("\n配置已保存: %s\n", yamlPath.c_str());

    return 0;
}
