#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string_view>

namespace stm32_control {
struct Packet {
    std::array<uint8_t, 8> bytes{};
    size_t size = 0;
};

inline std::optional<Packet> BuildDeviceCommand(std::string_view device, bool on) {
    uint8_t command;
    if (device == "light")
        command = on ? 0x01 : 0x02;
    else if (device == "fan")
        command = on ? 0x03 : 0x04;
    else if (device == "window")
        command = on ? 0x05 : 0x06;
    else if (device == "door")
        command = on ? 0x09 : 0x0A;
    else
        return std::nullopt;
    return Packet{{0xF4, 0x06, 0x07, 0xFB, 0xF4, 0x06, command, 0xFB}, 8};
}

inline std::optional<Packet> BuildModeCommand(std::string_view mode) {
    uint8_t command;
    if (mode == "manual")
        command = 0x07;
    else if (mode == "auto")
        command = 0x08;
    else if (mode == "sleep")
        command = 0x0B;
    else if (mode == "away")
        command = 0x0C;
    else
        return std::nullopt;
    return Packet{{0xF4, 0x06, command, 0xFB, 0, 0, 0, 0}, 4};
}
}  // namespace stm32_control
