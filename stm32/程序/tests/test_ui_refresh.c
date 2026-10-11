#include <assert.h>
#include <stdint.h>
#include "../USER/ui_refresh.h"

int main(void)
{
    UiRefresh cache = {0};
    UiState state = {{0}};
    assert(UiRefresh_Need(&cache, &state, 0u, 0u));
    assert(!UiRefresh_Need(&cache, &state, 1000u, 0u));
    state.value[UI_TEMP] = 25u;
    assert(UiRefresh_Need(&cache, &state, 1000u, 0u));
    state.value[UI_TEMP] = 26u;
    assert(!UiRefresh_Need(&cache, &state, 1001u, 0u));
    assert(UiRefresh_Need(&cache, &state, 1200u, 0u));
    /* Menu/key feedback bypasses the sensor-display refresh limit. */
    assert(UiRefresh_Need(&cache, &state, 1201u, 1u));
    UiRefresh_Invalidate(&cache);
    assert(UiRefresh_Need(&cache, &state, UINT32_MAX - 100u, 0u));
    state.value[UI_MODE] = 1u;
    assert(!UiRefresh_Need(&cache, &state, 50u, 0u));
    assert(UiRefresh_Need(&cache, &state, 100u, 0u));
    return 0;
}
