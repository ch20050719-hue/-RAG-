#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "voice_command.h"

static void send_frame(volatile VoiceCommandState *state, uint8_t command,
                       uint32_t started_ms)
{
    VoiceCommand_ReceiveByte(state, 0xF4u, started_ms);
    VoiceCommand_ReceiveByte(state, 0x06u, started_ms + 1u);
    VoiceCommand_ReceiveByte(state, command, started_ms + 2u);
    VoiceCommand_ReceiveByte(state, 0xFBu, started_ms + 3u);
}

int main(void)
{
    VoiceCommandState state = {0};
    uint8_t command = 0u;
    uint8_t i;

    send_frame(&state, 0x05u, 10u);
    send_frame(&state, 0x06u, 20u);
    assert(VoiceCommand_Take(&state, 30u, &command) && command == 0x05u);
    assert(VoiceCommand_Take(&state, 30u, &command) && command == 0x06u);
    assert(!VoiceCommand_Take(&state, 30u, &command));

    VoiceCommand_ReceiveByte(&state, 0xF4u, 100u);
    VoiceCommand_ReceiveByte(&state, 0x99u, 101u);
    VoiceCommand_ReceiveByte(&state, 0x09u, 102u);
    VoiceCommand_ReceiveByte(&state, 0xFBu, 103u);
    VoiceCommand_ReceiveByte(&state, 0xF4u, 110u);
    VoiceCommand_ReceiveByte(&state, 0x06u, 111u);
    VoiceCommand_ReceiveByte(&state, 0x09u, 112u);
    VoiceCommand_ReceiveByte(&state, 0xFAu, 113u);
    send_frame(&state, 0xFFu, 120u);
    assert(!VoiceCommand_Take(&state, 130u, &command));

    VoiceCommand_ReceiveByte(&state, 0xF4u, 200u);
    VoiceCommand_ReceiveByte(&state, 0x06u, 201u);
    send_frame(&state, 0x09u, 400u);
    assert(VoiceCommand_Take(&state, 410u, &command) && command == 0x09u);

    VoiceCommand_ReceiveByte(&state, 0xF4u, 500u);
    VoiceCommand_ReceiveByte(&state, 0x06u, 501u);
    VoiceCommand_ReceiveByte(&state, 0xF4u, 502u);
    VoiceCommand_ReceiveByte(&state, 0x06u, 503u);
    VoiceCommand_ReceiveByte(&state, 0x0Au, 504u);
    VoiceCommand_ReceiveByte(&state, 0xFBu, 505u);
    assert(VoiceCommand_Take(&state, 510u, &command) && command == 0x0Au);

    for (i = 0u; i < VOICE_COMMAND_CAPACITY; ++i) {
        send_frame(&state, (uint8_t)((i % 12u) + 1u), 1000u + i * 5u);
    }
    send_frame(&state, 0x09u, 1100u);
    assert(state.count == VOICE_COMMAND_CAPACITY);
    assert(state.overflow_count == 1u);
    for (i = 0u; i < VOICE_COMMAND_CAPACITY; ++i) {
        assert(VoiceCommand_Take(&state, 1200u, &command));
        assert(command == (uint8_t)((i % 12u) + 1u));
    }
    assert(!VoiceCommand_Take(&state, 1200u, &command));

    send_frame(&state, 0x09u, 2000u);
    assert(!VoiceCommand_Take(&state, 7100u, &command));
    assert(state.expired_count == 1u);

    puts("voice command tests passed");
    return 0;
}
