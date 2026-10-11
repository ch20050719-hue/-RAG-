#ifndef TEST_OLED_DHT11_H
#define TEST_OLED_DHT11_H
#include "stm32f10x.h"
#define DHT11_READ_OK 0u
u8 DHT11_Read_Data(u8 *humi, u8 *temp);
#endif
