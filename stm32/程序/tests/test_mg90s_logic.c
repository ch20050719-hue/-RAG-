#include <assert.h>
#include <stdint.h>

#include "../HARDWARE/Servo/mg90s_logic.h"

int main(void)
{
    MG90S_LogicState state = {0u, MG90S_TARGET_OFF};
    uint16_t tick;

    state = MG90S_Logic_Request(state, MG90S_TARGET_OPEN);
    assert(state.target == MG90S_TARGET_OPEN);
    assert(state.remaining_ms == MG90S_ACTION_HOLD_MS);

    for (tick = 0u; tick < MG90S_ACTION_HOLD_MS - 1u; ++tick) {
        state = MG90S_Logic_Tick(state);
    }
    assert(state.target == MG90S_TARGET_OPEN);
    assert(state.remaining_ms == 1u);

    state = MG90S_Logic_Tick(state);
    assert(state.target == MG90S_TARGET_OFF);
    assert(state.remaining_ms == 0u);

    state = MG90S_Logic_Tick(state);
    assert(state.target == MG90S_TARGET_OFF);
    assert(state.remaining_ms == 0u);

    state = MG90S_Logic_Request(state, MG90S_TARGET_CLOSE);
    assert(state.target == MG90S_TARGET_CLOSE);
    assert(state.remaining_ms == MG90S_ACTION_HOLD_MS);

    state = MG90S_Logic_Tick(state);
    state = MG90S_Logic_Request(state, MG90S_TARGET_CLOSE);
    assert(state.target == MG90S_TARGET_CLOSE);
    assert(state.remaining_ms == MG90S_ACTION_HOLD_MS - 1u);

    state = MG90S_Logic_Request(state, 99u);
    assert(state.target == MG90S_TARGET_OFF);
    assert(state.remaining_ms == 0u);

    state = MG90S_Logic_Request(state, MG90S_TARGET_OPEN);
    state = MG90S_Logic_Request(state, MG90S_TARGET_OFF);
    assert(state.target == MG90S_TARGET_OFF);
    assert(state.remaining_ms == 0u);

    return 0;
}
