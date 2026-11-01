#include "protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static DoorResult send(Door d, const char *s, uint32_t t, const char *reply)
{
    DoorResult r = door_request(d, s, t);
    if (strcmp(r.reply, reply) != 0)
        fprintf(stderr, "request=%s time=%lu\nexpected=%sactual=%s",
            s, (unsigned long)t, reply, r.reply);
    assert(strcmp(r.reply, reply) == 0);
    return r;
}
int main(void)
{
    Door d = {0};
    DoorResult r;
    DoorLine line = {0};
    unsigned i;
    r = send(d, "1 OPEN 1000", 0, "ACK 1 NOT_ARMED\r\n");
    assert(!r.state.target);
    d = send(r.state, "2 ARM 5000", 10, "ACK 2 ARMED\r\n").state;
    assert(d.armed && !d.target);
    d = send(d, "3 OPEN 1000", 20, "ACK 3 TARGET_OPEN_COMMANDED\r\n").state;
    assert(d.target == 1);
    r = send(d, "3 OPEN 1000", 100, "DUP 3 TARGET_OPEN_COMMANDED\r\n");
    assert(r.state.motion_start == 20);
    send(d, "3 CLOSE 1000", 100, "ERR 3 ID_CONFLICT\r\n");
    send(d, "2 ARM 5000", 100, "ERR 2 ID_STALE\r\n");
    assert(door_tick(d, 1019).target == 1);
    d = door_tick(d, 1020);
    assert(!d.target && !d.armed);
    r = send(d, "3 OPEN 1000", 1100, "DUP 3 TARGET_OPEN_COMMANDED\r\n");
    assert(!r.state.target);
    d = send(d, "4 ARM 100", 2000, "ACK 4 ARMED\r\n").state;
    d = send(d, "5 CLOSE 5000", 2010, "ACK 5 TARGET_CLOSE_COMMANDED\r\n").state;
    assert(d.target == 2 && !door_tick(d, 2100).target);
    d = send(d, "6 DISARM 0", 2020, "ACK 6 PWM_DISABLED\r\n").state;
    assert(!d.armed && !d.target);
    {
        Door status = {0};
        status = send(status, "1 STATUS 0", 0,
            "ACK 1 STATE PROTO=1 ARM=0 TARGET=OFF ARM_LEFT_MS=0 ACTION_LEFT_MS=0\r\n").state;
        status = send(status, "2 ARM 5000", 10, "ACK 2 ARMED\r\n").state;
        status = send(status, "3 OPEN 1000", 20,
            "ACK 3 TARGET_OPEN_COMMANDED\r\n").state;
        r = send(status, "4 STATUS 0", 21,
            "ACK 4 STATE PROTO=1 ARM=1 TARGET=OPEN ARM_LEFT_MS=4989 ACTION_LEFT_MS=999\r\n");
        status = r.state;
        r = send(status, "4 STATUS 0", 31,
            "DUP 4 STATE PROTO=1 ARM=1 TARGET=OPEN ARM_LEFT_MS=4979 ACTION_LEFT_MS=989\r\n");
        assert(r.state.target == 1 && r.state.motion_start == 20);
        status = send(status, "5 STATUS 0", 5010,
            "ACK 5 STATE PROTO=1 ARM=0 TARGET=OFF ARM_LEFT_MS=0 ACTION_LEFT_MS=0\r\n").state;
        assert(!status.target && !status.armed);
    }
    {
        Door max_id = {0};
        max_id = send(max_id, "1 ARM 5000", 0, "ACK 1 ARMED\r\n").state;
        max_id = send(max_id, "2 CLOSE 5000", 0,
            "ACK 2 TARGET_CLOSE_COMMANDED\r\n").state;
        r = send(max_id, "4294967295 STATUS 0", 0,
            "ACK 4294967295 STATE PROTO=1 ARM=1 TARGET=CLOSE ARM_LEFT_MS=5000 ACTION_LEFT_MS=5000\r\n");
        assert(strlen(r.reply) < sizeof(r.reply));
    }
    {
        const char *bad[] = {"", "0 ARM 100", "7 ARM 99", "7 OPEN 5001",
            "7 DISARM 1", "7 STATUS 1", "7 ARM -1", "4294967296 ARM 100", "7 ARM 4294967296",
            "7 arm 100", "7 ARM 100 x", "7  ARM 100", "7 ARM 100 ", "x ARM 100"};
        for (i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
            r = door_request(d, bad[i], 2030);
            assert(strcmp(r.reply, "ERR 0 BAD_REQUEST\r\n") == 0);
            assert(r.state.last_id == d.last_id);
        }
    }
    d = send(d, "7 ARM 100", UINT32_MAX-49u, "ACK 7 ARMED\r\n").state;
    assert(door_tick(d, 49).armed);
    assert(!door_tick(d, 50).armed);
    for (i = 0; i < 100; ++i) assert(door_feed(&line, 'X') == 0);
    assert(door_feed(&line, '\n') == -1);
    assert(door_feed(&line, '1') == 0);
    assert(door_feed(&line, '\r') == 0);
    assert(door_feed(&line, '\n') == 1 && strcmp(line.text, "1") == 0);
    assert(door_feed(&line, 0) == 0);
    assert(door_feed(&line, '\n') == -1);
    assert(door_feed(&line, 'A') == 0);
    assert(door_feed(&line, '\r') == 0);
    assert(door_feed(&line, 'B') == 0);
    assert(door_feed(&line, '\n') == -1);
    puts("protocol tests passed");
    return 0;
}
