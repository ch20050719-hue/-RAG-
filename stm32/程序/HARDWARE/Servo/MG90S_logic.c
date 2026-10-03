#include "MG90S_logic.h"

MG90S_LogicState MG90S_Logic_Request(MG90S_LogicState state, uint8_t target)
{
    if (target != MG90S_TARGET_OPEN && target != MG90S_TARGET_CLOSE) {
        state.target = MG90S_TARGET_OFF;
        state.remaining_ms = 0u;
        return state;
    }

    if (state.target == target && state.remaining_ms > 0u) {
        return state;
    }

    state.target = target;
    state.remaining_ms = MG90S_ACTION_HOLD_MS;
    return state;
}

MG90S_LogicState MG90S_Logic_Tick(MG90S_LogicState state)
{
    if (state.target == MG90S_TARGET_OFF || state.remaining_ms == 0u) {
        state.target = MG90S_TARGET_OFF;
        state.remaining_ms = 0u;
        return state;
    }

    --state.remaining_ms;
    if (state.remaining_ms == 0u) {
        state.target = MG90S_TARGET_OFF;
    }

    return state;
}
