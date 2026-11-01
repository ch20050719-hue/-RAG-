#include "board.h"
#include "protocol.h"
static Door door;
static DoorLine line;

static void service(void)
{
    door = door_tick(door, board_millis());
    board_target(door.target);
}

/* Bounded TX wait; keep processing lease expiry even with a stalled UART. */
static void reply(const char *s)
{
    uint32_t start = board_millis();
    while (*s) {
        service();
        if ((uint32_t)(board_millis()-start) >= 20u) return;
        if (USART1_SR & (1u<<7)) USART1_DR = (uint32_t)(unsigned char)*s++;
    }
}

int main(void)
{
    board_init();
    reply("READY PWM_DISABLED\r\n");
    for (;;) {
        uint32_t status;
        service();
        status = USART1_SR;
        if (status & 0x2Fu) {
            unsigned char byte = (unsigned char)USART1_DR;
            int complete;
            if (status & 15u) line.bad = 1; /* SR then DR clears UART errors. */
            complete = door_feed(&line, byte);
            if (complete < 0) reply("ERR 0 BAD_LINE\r\n");
            else if (complete > 0) {
                DoorResult r = door_request(door, line.text, board_millis());
                door = r.state;
                board_target(door.target);
                reply(r.reply);
            }
        }
    }
}
