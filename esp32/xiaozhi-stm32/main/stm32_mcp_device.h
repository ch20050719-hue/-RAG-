#pragma once

#include "mcp_server.h"
#include "stm32_uart_device.h"

class STM32Mcp {
    static ReturnValue Submit(const std::optional<stm32_control::Packet>& packet) {
        if (!packet)
            throw std::invalid_argument("不支持的设备或模式");
        const esp_err_t err = stm32_uart_submit(*packet);
        if (err != ESP_OK) {
            throw std::runtime_error(std::string("控制指令未入队：") + esp_err_to_name(err));
        }
        return std::string("指令已加入串口发送队列，尚未确认 STM32 执行或设备到位。");
    }

public:
    static void Register() {
        auto& server = McpServer::GetInstance();
        server.AddTool("self.stm32.get_environment",
                       "读取 STM32 最近采集的室内温度(℃)、湿度(%RH)和相对光照原始值。"
                       "每次回答环境问题先调用此工具。有效期 3000ms；无效或过期数据为 null，"
                       "不得将其当作 0 或推测实时环境。light_raw 未标定，不是 lux，"
                       "不得按未经标定的阈值判断明暗；这些数据不能判断空气质量或是否有人。",
                       PropertyList(), [](const PropertyList&) -> ReturnValue {
                           return stm32_environment::ToJson(stm32_uart_get_environment());
                       });
        server.AddTool(
            "self.stm32.set_device",
            "控制 STM32 智能家居。device 只能为 light(灯)、fan(风扇)、window(窗户)、door(门)；"
            "on 为 true 打开、false 关闭。执行前切换手动模式并退出睡眠/离家场景。"
            "从自动切手动会先关闭灯、风扇、窗户并停止蜂鸣器，再执行指定动作。"
            "返回入队结果，不表示设备已到位。",
            PropertyList(
                {Property("device", kPropertyTypeString), Property("on", kPropertyTypeBoolean)}),
            [](const PropertyList& params) -> ReturnValue {
                return Submit(stm32_control::BuildDeviceCommand(
                    params["device"].value<std::string>(), params["on"].value<bool>()));
            });
        server.AddTool(
            "self.stm32.set_mode",
            "切换 STM32 模式。mode 只能为 manual(手动)、auto(自动)、sleep(睡眠)、away(离家)。"
            "手动：由指令控制；从自动切手动会关灯、关风扇、关窗并停蜂鸣器。"
            "自动：恢复 STM32 的传感器阈值控制。"
            "睡眠：手动、开风扇、关灯、关门，不改变窗户。"
            "离家：手动、关灯、关风扇、关门，不改变窗户。"
            "返回入队结果，不表示设备已到位。",
            PropertyList({Property("mode", kPropertyTypeString)}),
            [](const PropertyList& params) -> ReturnValue {
                return Submit(stm32_control::BuildModeCommand(params["mode"].value<std::string>()));
            });
    }
};
