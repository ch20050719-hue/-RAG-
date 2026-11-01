#ifndef TEST_TIM2_H
#define TEST_TIM2_H
#include "menu.h"
#define USART2 ((void *)2)
#define USART_FLAG_TC 1
#define USART_FLAG_TXE 2
#define RESET 0
#define HOME_SCENE_NORMAL 0u
#define HOME_SCENE_SLEEP 1u
#define HOME_SCENE_AWAY 2u
void USART_SendData(void *port, uint16_t value);
int USART_GetFlagStatus(void *port, uint16_t flag);
void __set_FAULTMASK(int mask);
void NVIC_SystemReset(void);
void HomeScene_Apply(uint8_t scene);
void HomeControl_SyncMode(void);
uint8_t HomeScene_GetCurrent(void);
#endif
