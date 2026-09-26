#ifndef __TIM2_H__
#define __TIM2_H__

#include "stm32f10x.h"                  // Device header
#include "menu.h"
#include "buzzer.h"
#include "key.h"

extern u8 Menu;
extern u8 modeee;
extern u8 Temp_value;
extern u8 Humi_value;
extern uint16_t Lux_value;
extern uint16_t Smoke_value;

#define HOME_SCENE_NORMAL 0u
#define HOME_SCENE_SLEEP  1u
#define HOME_SCENE_AWAY   2u

#define HOME_SCENE_CMD_SLEEP 0x0Bu
#define HOME_SCENE_CMD_AWAY  0x0Cu

void AppTimer1_Init(u16 Prescaler, u16 Period);
void HomeScene_Apply(uint8_t scene);
uint8_t HomeScene_GetCurrent(void);

#endif
