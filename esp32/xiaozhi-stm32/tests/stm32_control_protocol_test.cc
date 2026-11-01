#include "stm32_control_protocol.h"

#include <cstdlib>
#include <iostream>
#include <string_view>

#ifdef WITH_STM32_RECEIVER
extern "C" {
#include "voice_command.h"
}
#endif

namespace {
int checks = 0;
void Check(bool condition, const char* message) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}

void CheckFrame(const stm32_control::Packet& packet, size_t offset, uint8_t command) {
    Check(packet.bytes[offset] == 0xF4, "frame header");
    Check(packet.bytes[offset + 1] == 0x06, "frame type");
    Check(packet.bytes[offset + 2] == command, "command mapping");
    Check(packet.bytes[offset + 3] == 0xFB, "frame trailer");
}

#ifdef WITH_STM32_RECEIVER
void CheckReceived(const stm32_control::Packet& packet, uint8_t command, bool device) {
    VoiceCommandState receiver{};
    uint32_t now = 0;
    uint8_t received = 0;
    // Feed bytes individually, exactly as the USART interrupt does.
    for (size_t i = 0; i < packet.size; ++i) {
        VoiceCommand_ReceiveByte(&receiver, packet.bytes[i], ++now);
    }
    if (device) {
        Check(VoiceCommand_Take(&receiver, now, &received) == 1, "manual frame received");
        Check(received == 0x07, "manual frame precedes device action");
    }
    Check(VoiceCommand_Take(&receiver, now, &received) == 1, "action or mode received");
    Check(received == command, "real STM32 receiver decodes requested command");
    Check(VoiceCommand_Take(&receiver, now, &received) == 0, "no extra command");
}
#endif

void TestDevices() {
    struct Case { std::string_view name; uint8_t on; uint8_t off; };
    const Case cases[] = {{"light", 1, 2}, {"fan", 3, 4},
                          {"window", 5, 6}, {"door", 9, 10}};
    for (const auto& item : cases) {
        for (bool on : {false, true}) {
            const auto packet = stm32_control::BuildDeviceCommand(item.name, on);
            Check(packet.has_value(), "valid device accepted");
            Check(packet->size == 8, "device sends exactly two frames");
            const uint8_t command = on ? item.on : item.off;
            CheckFrame(*packet, 0, 7);
            CheckFrame(*packet, 4, command);
#ifdef WITH_STM32_RECEIVER
            CheckReceived(*packet, command, true);
#endif
        }
    }
}

void TestModes() {
    struct Case { std::string_view name; uint8_t command; };
    const Case cases[] = {{"manual", 7}, {"auto", 8}, {"sleep", 11}, {"away", 12}};
    for (const auto& item : cases) {
        const auto packet = stm32_control::BuildModeCommand(item.name);
        Check(packet.has_value(), "valid mode accepted");
        Check(packet->size == 4, "mode sends exactly one frame without manual prefix");
        CheckFrame(*packet, 0, item.command);
#ifdef WITH_STM32_RECEIVER
        CheckReceived(*packet, item.command, false);
#endif
    }
}

void TestInvalidInputs() {
    for (std::string_view input : {"", "Light", "light ", " fan", "lamp", "manual",
                                  "light;door", "0x01"}) {
        Check(!stm32_control::BuildDeviceCommand(input, false), "invalid device rejected (off)");
        Check(!stm32_control::BuildDeviceCommand(input, true), "invalid device rejected (on)");
    }
    for (std::string_view input : {"", "AUTO", "auto ", " sleep", "automatic", "light",
                                  "auto;away", "0x08"}) {
        Check(!stm32_control::BuildModeCommand(input), "invalid mode rejected");
    }
    Check(!stm32_control::BuildDeviceCommand(std::string_view("door\0extra", 10), true),
          "embedded NUL does not bypass device whitelist");
    Check(!stm32_control::BuildModeCommand(std::string_view("auto\0extra", 10)),
          "embedded NUL does not bypass mode whitelist");
#ifdef WITH_STM32_RECEIVER
    VoiceCommandState receiver{};
    uint8_t command = 0;
    uint32_t now = 0;
    const uint8_t invalidCommands[] = {0x00, 0x0D, 0xFF};
    for (uint8_t invalid : invalidCommands) {
        const uint8_t frame[] = {0xF4, 0x06, invalid, 0xFB};
        for (uint8_t byte : frame) VoiceCommand_ReceiveByte(&receiver, byte, ++now);
        Check(VoiceCommand_Take(&receiver, now, &command) == 0, "STM32 rejects invalid command");
    }
#endif
}
}  // namespace

int main() {
    TestDevices();
    TestModes();
    TestInvalidInputs();
    std::cout << "PASS: " << checks << " runtime checks";
#ifdef WITH_STM32_RECEIVER
    std::cout << " including real STM32 voice_command.c integration";
#endif
    std::cout << '\n';
}
