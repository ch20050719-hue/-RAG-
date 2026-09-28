#ifndef TEST_TIM2_H
#define TEST_TIM2_H
#include "menu.h"
#define USART2 ((void *)2)
#define USART_FLAG_TC 1
#define USART_FLAG_TXE 2
#define RESET 0
void USART_SendData(void *port, uint16_t value);
int USART_GetFlagStatus(void *port, uint16_t flag);
void __set_FAULTMASK(int mask);
void NVIC_SystemReset(void);
#endif
