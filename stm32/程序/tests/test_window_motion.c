#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "window_motion.h"

int main(void)
{
    WindowMotionState state = {0u, 0u};
    WindowMotionTick tick;
    uint16_t i;

    state = WindowMotion_Request(state, 1u);
    assert(state.target == WINDOW_MOTION_STEPS);
    for (i = 0u; i < WINDOW_MOTION_STEPS; ++i) {
        tick = WindowMotion_Next(state);
        assert(tick.phase == (uint8_t)((i % 8u) + 1u));
        state = tick.state;
        assert(state.position == i + 1u);
    }
    assert(WindowMotion_Next(state).phase == 0u);

    state = WindowMotion_Request(state, 0u);
    for (i = WINDOW_MOTION_STEPS; i > 0u; --i) {
        tick = WindowMotion_Next(state);
        assert(tick.phase == (uint8_t)(((i - 1u) % 8u) + 1u));
        state = tick.state;
    }
    assert(state.position == 0u);
    assert(WindowMotion_Next(state).phase == 0u);

    state = WindowMotion_Request(state, 1u);
    for (i = 0u; i < 100u; ++i) {
        state = WindowMotion_Next(state).state;
    }
    state = WindowMotion_Request(state, 1u);
    assert(state.position == 100u);
    state = WindowMotion_Request(state, 0u);
    for (i = 100u; i > 0u; --i) {
        state = WindowMotion_Next(state).state;
    }
    assert(state.position == 0u);
    assert(WindowMotion_Next(state).phase == 0u);

    puts("window motion tests passed");
    return 0;
}
