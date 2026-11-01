#ifndef TEST_MENU_H
#define TEST_MENU_H
#include <stdint.h>
typedef uint8_t u8;
extern u8 Humi, Temp, modeee;
extern volatile u8 DHT11_DataValid, ADC_DataValid;
extern uint16_t Lux, Smoke;
extern u8 Temp_value, Humi_value;
extern uint16_t Lux_value, Smoke_value;
#endif
