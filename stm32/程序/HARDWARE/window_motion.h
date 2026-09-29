#ifndef WINDOW_MOTION_H
#define WINDOW_MOTION_H

#include <stdint.h>

/* Keep the existing 180-degree command: 256 cycles of eight half-steps. */
#define WINDOW_MOTION_STEPS 2048u

typedef struct {
    uint16_t position;
    uint16_t target;
} WindowMotionState;

typedef struct {
    WindowMotionState state;
    uint8_t phase; /* 1..8 for a step, 0 when the target is reached. */
} WindowMotionTick;

WindowMotionState WindowMotion_Request(WindowMotionState state, uint8_t open);
WindowMotionTick WindowMotion_Next(WindowMotionState state);

#endif
