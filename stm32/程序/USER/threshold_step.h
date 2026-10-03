#ifndef THRESHOLD_STEP_H
#define THRESHOLD_STEP_H

#include <stdint.h>

static uint8_t Threshold_Up8(uint8_t value)
{
    return value >= 100u ? 100u : (uint8_t)(value + 1u);
}

static uint8_t Threshold_Down8(uint8_t value)
{
    return value > 0u ? (uint8_t)(value - 1u) : 0u;
}

static uint16_t Threshold_Up16(uint16_t value)
{
    return value >= 1990u ? 2000u : (uint16_t)(value + 10u);
}

static uint16_t Threshold_Down16(uint16_t value)
{
    return value >= 10u ? (uint16_t)(value - 10u) : 0u;
}

#endif
