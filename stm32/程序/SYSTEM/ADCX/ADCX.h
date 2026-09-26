#ifndef _ADCX_H_
#define _ADCX_H_

#include "stm32f10x.h"                  // Device header

void Adc1_Channe_Init(void);
u16 get_Adc_Value(u8 ch);

#endif
