#ifndef VOICE_COMMAND_H
#define VOICE_COMMAND_H

#include <stdint.h>

#define VOICE_COMMAND_CAPACITY 16u
#define VOICE_FRAME_TIMEOUT_MS 100u
#define VOICE_COMMAND_MAX_AGE_MS 5000u

typedef struct {
    uint8_t frame_state;
    uint8_t frame_command;
    uint32_t last_byte_ms;
    uint8_t commands[VOICE_COMMAND_CAPACITY];
    uint32_t received_ms[VOICE_COMMAND_CAPACITY];
    uint8_t head;
    uint8_t tail;
    uint8_t count;
    uint16_t overflow_count;
    uint16_t expired_count;
} VoiceCommandState;

void VoiceCommand_ReceiveByte(volatile VoiceCommandState *state,
                              uint8_t byte, uint32_t now_ms);
uint8_t VoiceCommand_Take(volatile VoiceCommandState *state,
                          uint32_t now_ms, uint8_t *command);

#endif
