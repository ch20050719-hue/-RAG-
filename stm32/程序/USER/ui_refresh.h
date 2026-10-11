#ifndef UI_REFRESH_H
#define UI_REFRESH_H
#include <stdint.h>
#include <string.h>

enum {
    UI_MENU, UI_SCREEN, UI_SELECTION, UI_PAGE, UI_SETTING,
    UI_TEMP, UI_HUMI, UI_LUX, UI_SMOKE, UI_DHT_VALID, UI_ADC_VALID,
    UI_TEMP_LIMIT, UI_HUMI_LIMIT, UI_LUX_LIMIT, UI_SMOKE_LIMIT,
    UI_LIGHT, UI_FAN, UI_WINDOW, UI_DOOR, UI_SCENE, UI_MODE, UI_MOTION,
    UI_VALUE_COUNT
};
typedef struct { uint16_t value[UI_VALUE_COUNT]; } UiState;
typedef struct {
    UiState displayed;
    uint32_t last_ms;
    uint8_t valid;
} UiRefresh;

static void UiRefresh_Invalidate(UiRefresh *cache)
{
    cache->valid = 0u;
}

/* Keep event feedback immediate; redraw changing telemetry at most every 200 ms. */
static uint8_t UiRefresh_Need(UiRefresh *cache, const UiState *state,
                              uint32_t now, uint8_t event)
{
    if (cache->valid && !event &&
        ((uint32_t)(now - cache->last_ms) < 200u ||
         memcmp(&cache->displayed, state, sizeof(*state)) == 0))
        return 0u;
    cache->displayed = *state;
    cache->last_ms = now;
    cache->valid = 1u;
    return 1u;
}
#endif
