#include <assert.h>
#include "auto_control_logic.h"

int main(void)
{
    AutoControlState state = {0u, 0u, 0u, 0u};
    AutoControlInputs input = {40u, 80u, 80u, 2000u, 40u, 80u, 80u, 2000u, 1u, 1u};
    state = AutoControl_Evaluate(state, input);
    assert(!state.temperature && !state.humidity && !state.light && !state.smoke);
    input.temperature = 41u; input.humidity = 81u;
    input.light = 79u; input.smoke = 2001u;
    state = AutoControl_Evaluate(state, input);
    assert(state.temperature && state.humidity && state.light && state.smoke);
    input.temperature = 39u; input.humidity = 78u;
    input.light = 129u; input.smoke = 1901u;
    state = AutoControl_Evaluate(state, input);
    assert(state.temperature && state.humidity && state.light && state.smoke);
    input.temperature = 38u; input.humidity = 77u;
    input.light = 130u; input.smoke = 1900u;
    input.dht_valid = 0u; input.adc_valid = 0u;
    state = AutoControl_Evaluate(state, input);
    assert(state.temperature && state.humidity && state.light && state.smoke);
    input.dht_valid = 1u; input.adc_valid = 1u;
    state = AutoControl_Evaluate(state, input);
    assert(!state.temperature && !state.humidity && !state.light && !state.smoke);
    /* Near-zero thresholds must recover at zero instead of unsigned wrap. */
    assert(AutoControl_High(1u, 0u, 1u, 2u) == 0u);
    assert(AutoControl_High(0u, 1u, 0u, 2u) == 1u);
    assert(AutoControl_Low(1u, 65535u, 65530u, 50u) == 0u);
    assert(AutoControl_Low(0u, 0u, 0u, 50u) == 0u);
    return 0;
}
