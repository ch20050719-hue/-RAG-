#ifndef MG90S_LOGIC_H
#define MG90S_LOGIC_H

#include <stdint.h>

#define MG90S_ACTION_HOLD_MS 1000u

#define MG90S_TARGET_OFF 0u
#define MG90S_TARGET_OPEN 1u
#define MG90S_TARGET_CLOSE 2u

typedef struct {
    uint16_t remaining_ms;
    uint8_t target;
} MG90S_LogicState;

MG90S_LogicState MG90S_Logic_Request(MG90S_LogicState state, uint8_t target);
MG90S_LogicState MG90S_Logic_Tick(MG90S_LogicState state);

#endif
