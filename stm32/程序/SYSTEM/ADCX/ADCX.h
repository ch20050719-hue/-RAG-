#ifndef _ADCX_H_
#define _ADCX_H_

#include "stm32f10x.h"                  // Device header

u8 Adc1_Channe_Init(void);
u8 ADCX_ReadValue(u8 ch, u16 *value);

#endif
