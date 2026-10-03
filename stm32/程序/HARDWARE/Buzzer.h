#ifndef __BUZZER_H
#define __BUZZER_H

#include "stm32f10x.h"                  // Device header

#define Buzzer		GPIO_Pin_5

extern u8 Buzzer_Flag;

void Buzzer_Init(void);
void Buzzer_ON(void);
void Buzzer_OFF(void);

#endif
