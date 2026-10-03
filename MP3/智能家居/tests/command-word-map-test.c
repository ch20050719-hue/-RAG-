#include <stdint.h>
#include <stdio.h>
#include <stddef.h>

#define VMUP_MSG_HEAD_LOW 0xF4
#define VMUP_MSG_HEAD_HIGH 0xF5
#define VMUP_MSG_TAIL 0xFB

static uint16_t active_id;
static uint8_t sent[8];
static size_t sent_count;

typedef uint16_t cmd_handle_t;

uint16_t cmd_info_get_command_id(cmd_handle_t handle)
{
    (void)handle;
    return active_id;
}

void vmup_port_send_char(uint16_t value)
{
    if (sent_count < sizeof(sent))
    {
        sent[sent_count++] = (uint8_t)value;
    }
}

static void invoke_command_hook(uint16_t id)
{
    cmd_handle_t cmd_handle = 0;
    active_id = id;
    sent_count = 0;

#include "../Code/command-word.c"
}

int main(void)
{
    static const struct
    {
        uint16_t id;
        uint8_t expected_command;
    } cases[] = {
        {3, 0x01}, {4, 0x02}, {5, 0x03}, {6, 0x04},
        {7, 0x05}, {8, 0x06}, {9, 0x07}, {10, 0x08},
        {11, 0x0C}, {12, 0x0B}, {13, 0x09}, {14, 0x0A}
    };

    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
    {
        invoke_command_hook(cases[i].id);
        if (sent_count != 4 || sent[0] != VMUP_MSG_HEAD_LOW ||
            sent[1] != VMUP_MSG_HEAD_HIGH ||
            sent[2] != cases[i].expected_command ||
            sent[3] != VMUP_MSG_TAIL)
        {
            fprintf(stderr, "mapping failed for command id %u\n", cases[i].id);
            return 1;
        }
    }

    static const uint16_t unmapped_ids[] = {0, 1, 2, 15, 0xFFFF};
    for (size_t i = 0; i < sizeof(unmapped_ids) / sizeof(unmapped_ids[0]); ++i)
    {
        invoke_command_hook(unmapped_ids[i]);
        if (sent_count != 0)
        {
            fprintf(stderr, "unexpected frame for command id %u\n", unmapped_ids[i]);
            return 2;
        }
    }

    puts("command ID mapping tests passed");
    return 0;
}
