#ifndef ENVIRONMENT_PROTOCOL_H
#define ENVIRONMENT_PROTOCOL_H
#include <stdint.h>

#define ENVIRONMENT_FRAME_SIZE 20u
#define ENVIRONMENT_FRAME_HEAD 0xF4u
#define ENVIRONMENT_FRAME_TYPE 0x08u
#define ENVIRONMENT_FRAME_VERSION 0x02u
#define ENVIRONMENT_FRAME_TAIL 0xFBu
#define ENVIRONMENT_MAX_AGE_MS 3000u
#define ENVIRONMENT_DHT_VALID 0x01u
#define ENVIRONMENT_ADC_VALID 0x02u

typedef struct {
    uint8_t dht_valid;
    uint8_t adc_valid;
    uint8_t temperature_c;
    uint8_t humidity_percent;
    uint16_t light_raw;
    uint32_t dht_age_ms;
    uint32_t adc_age_ms;
    uint16_t smoke_raw;
} EnvironmentSnapshot;

/* Light is 4096 - ADC, not calibrated lux; smoke is ADC, not ppm.
 * Invalid values keep
 * their bytes for diagnosis; consumers must obey flags and sample ages. */
static __inline uint8_t Environment_Encode(const EnvironmentSnapshot *sample,
                                  uint8_t frame[ENVIRONMENT_FRAME_SIZE])
{
    uint8_t i;
    uint8_t flags = 0u;
    uint8_t checksum = 0u;
    if (sample == 0 || frame == 0) return 0u;
    if (sample->dht_valid && sample->dht_age_ms <= ENVIRONMENT_MAX_AGE_MS &&
        sample->temperature_c <= 50u && sample->humidity_percent <= 100u)
        flags |= ENVIRONMENT_DHT_VALID;
    if (sample->adc_valid && sample->adc_age_ms <= ENVIRONMENT_MAX_AGE_MS &&
        sample->light_raw >= 1u && sample->light_raw <= 4096u &&
        sample->smoke_raw <= 4095u) flags |= ENVIRONMENT_ADC_VALID;
    frame[0] = ENVIRONMENT_FRAME_HEAD;
    frame[1] = ENVIRONMENT_FRAME_TYPE;
    frame[2] = ENVIRONMENT_FRAME_VERSION;
    frame[3] = flags;
    frame[4] = sample->temperature_c;
    frame[5] = sample->humidity_percent;
    frame[6] = (uint8_t)sample->light_raw;
    frame[7] = (uint8_t)(sample->light_raw >> 8);
    frame[8] = (uint8_t)sample->smoke_raw;
    frame[9] = (uint8_t)(sample->smoke_raw >> 8);
    for (i = 0u; i < 4u; ++i) {
        frame[10u + i] = (uint8_t)(sample->dht_age_ms >> (8u * i));
        frame[14u + i] = (uint8_t)(sample->adc_age_ms >> (8u * i));
    }
    for (i = 1u; i <= 17u; ++i) checksum ^= frame[i];
    frame[18] = checksum;
    frame[19] = ENVIRONMENT_FRAME_TAIL;
    return 1u;
}
#endif
