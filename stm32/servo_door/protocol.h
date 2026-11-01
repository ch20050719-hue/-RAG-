#ifndef DOOR_PROTOCOL_H
#define DOOR_PROTOCOL_H
#include <stdint.h>
#define DOOR_LINE_CAP 64
#define DOOR_REPLY_CAP 96
#define DOOR_PROTOCOL_VERSION 1u
#define DOOR_TTL_MIN 100u
#define DOOR_TTL_MAX 5000u
typedef struct {
    uint32_t last_id, last_ttl, arm_start, arm_ttl, motion_start, motion_ttl;
    unsigned armed, target, last_command;
    const char *last_result;
} Door;
typedef struct {
    char text[DOOR_LINE_CAP];
    unsigned length, bad;
} DoorLine;
typedef struct { Door state; char reply[DOOR_REPLY_CAP]; } DoorResult;
/* Value-in/value-out state machine; target: 0 off, 1 open, 2 close. */
Door door_tick(Door state, uint32_t now);
DoorResult door_request(Door state, const char *line, uint32_t now);
/* 0 incomplete; 1 complete; -1 corrupt/overflow line discarded through LF. */
int door_feed(DoorLine *line, unsigned char byte);
#endif
