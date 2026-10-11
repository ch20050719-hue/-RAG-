#ifndef AUTO_CONTROL_LOGIC_H
#define AUTO_CONTROL_LOGIC_H
#include <stdint.h>

/* Recovery-side bands only; activation thresholds remain unchanged.
 * Provisional values require tuning against the existing physical sensors. */
#define AUTO_TEMP_RECOVERY_BAND 2u
#define AUTO_HUMI_RECOVERY_BAND 3u
#define AUTO_LIGHT_RECOVERY_BAND 50u
#define AUTO_SMOKE_RECOVERY_BAND 100u

typedef struct {
    uint8_t temperature, humidity, light, smoke;
} AutoControlState;

typedef struct {
    uint16_t temperature, humidity, light, smoke;
    uint16_t temperature_threshold, humidity_threshold;
    uint16_t light_threshold, smoke_threshold;
    uint8_t dht_valid, adc_valid;
} AutoControlInputs;

static uint8_t AutoControl_High(uint8_t active, uint16_t value,
                               uint16_t threshold, uint16_t band)
{
    uint16_t recovery = threshold > band ? (uint16_t)(threshold - band) : 0u;
    return active ? (uint8_t)(value > recovery) : (uint8_t)(value > threshold);
}

static uint8_t AutoControl_Low(uint8_t active, uint16_t value,
                              uint16_t threshold, uint16_t band)
{
    uint32_t recovery = (uint32_t)threshold + band;
    if (recovery > 65535u) recovery = 65535u;
    return active ? (uint8_t)(value < recovery) : (uint8_t)(value < threshold);
}

static AutoControlState AutoControl_Evaluate(AutoControlState previous,
                                            AutoControlInputs input)
{
    AutoControlState next = previous;
    if (input.dht_valid) {
        next.temperature = AutoControl_High(previous.temperature, input.temperature,
            input.temperature_threshold, AUTO_TEMP_RECOVERY_BAND);
        next.humidity = AutoControl_High(previous.humidity, input.humidity,
            input.humidity_threshold, AUTO_HUMI_RECOVERY_BAND);
    }
    if (input.adc_valid) {
        next.light = AutoControl_Low(previous.light, input.light,
            input.light_threshold, AUTO_LIGHT_RECOVERY_BAND);
        next.smoke = AutoControl_High(previous.smoke, input.smoke,
            input.smoke_threshold, AUTO_SMOKE_RECOVERY_BAND);
    }
    return next;
}
#endif
