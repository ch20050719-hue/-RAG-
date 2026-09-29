#include "voice_command.h"

static uint8_t VoiceCommand_NextIndex(uint8_t index)
{
    return (uint8_t)((index + 1u) % VOICE_COMMAND_CAPACITY);
}

static void VoiceCommand_Expire(volatile VoiceCommandState *state,
                                uint32_t now_ms)
{
    while (state->count > 0u &&
           (uint32_t)(now_ms - state->received_ms[state->head]) >
               VOICE_COMMAND_MAX_AGE_MS) {
        state->head = VoiceCommand_NextIndex(state->head);
        state->count--;
        if (state->expired_count != UINT16_MAX) state->expired_count++;
    }
}

static void VoiceCommand_Enqueue(volatile VoiceCommandState *state,
                                 uint8_t command, uint32_t now_ms)
{
    VoiceCommand_Expire(state, now_ms);
    if (state->count == VOICE_COMMAND_CAPACITY) {
        if (state->overflow_count != UINT16_MAX) state->overflow_count++;
        return;
    }
    state->commands[state->tail] = command;
    state->received_ms[state->tail] = now_ms;
    state->tail = VoiceCommand_NextIndex(state->tail);
    state->count++;
}

void VoiceCommand_ReceiveByte(volatile VoiceCommandState *state,
                              uint8_t byte, uint32_t now_ms)
{
    if (state->frame_state != 0u &&
        (uint32_t)(now_ms - state->last_byte_ms) > VOICE_FRAME_TIMEOUT_MS) {
        state->frame_state = 0u;
    }
    state->last_byte_ms = now_ms;

    switch (state->frame_state) {
        case 0u:
            if (byte == 0xF4u) state->frame_state = 1u;
            break;
        case 1u:
            if (byte == 0x06u) state->frame_state = 2u;
            else if (byte != 0xF4u) state->frame_state = 0u;
            break;
        case 2u:
            if (byte == 0xF4u) state->frame_state = 1u;
            else {
                state->frame_command = byte;
                state->frame_state = 3u;
            }
            break;
        default:
            if (byte == 0xFBu && state->frame_command >= 0x01u &&
                state->frame_command <= 0x0Cu) {
                VoiceCommand_Enqueue(state, state->frame_command, now_ms);
            }
            state->frame_state = byte == 0xF4u ? 1u : 0u;
            break;
    }
}

uint8_t VoiceCommand_Take(volatile VoiceCommandState *state,
                          uint32_t now_ms, uint8_t *command)
{
    if (command == 0) return 0u;
    VoiceCommand_Expire(state, now_ms);
    if (state->count == 0u) return 0u;
    *command = state->commands[state->head];
    state->head = VoiceCommand_NextIndex(state->head);
    state->count--;
    return 1u;
}
