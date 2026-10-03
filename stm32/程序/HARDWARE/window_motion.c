#include "window_motion.h"

WindowMotionState WindowMotion_Request(WindowMotionState state, uint8_t open)
{
    if (open <= 1u) {
        state.target = open ? WINDOW_MOTION_STEPS : 0u;
    }
    return state;
}

WindowMotionTick WindowMotion_Next(WindowMotionState state)
{
    WindowMotionTick result;
    result.state = state;
    result.phase = 0u;

    if (state.position < state.target) {
        result.phase = (uint8_t)((state.position % 8u) + 1u);
        result.state.position++;
    } else if (state.position > state.target) {
        result.phase = (uint8_t)(((state.position - 1u) % 8u) + 1u);
        result.state.position--;
    }
    return result;
}
