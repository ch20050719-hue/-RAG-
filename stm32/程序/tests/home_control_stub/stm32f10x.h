#ifndef HOME_TEST_STM32_H
#define HOME_TEST_STM32_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef struct { uint16_t TIM_ClockDivision, TIM_CounterMode, TIM_Period, TIM_Prescaler, TIM_RepetitionCounter; } TIM_TimeBaseInitTypeDef;
typedef struct { uint8_t NVIC_IRQChannel, NVIC_IRQChannelCmd, NVIC_IRQChannelPreemptionPriority, NVIC_IRQChannelSubPriority; } NVIC_InitTypeDef;
#define TIM1 1
#define TIM1_UP_IRQn 1
#define TIM_IT_Update 1
#define RCC_APB2Periph_TIM1 1
#define TIM_CKD_DIV1 0
#define TIM_CounterMode_Up 0
#define ENABLE 1
#define RESET 0
void RCC_APB2PeriphClockCmd(int clock, int enabled);
void TIM_TimeBaseInit(int timer, TIM_TimeBaseInitTypeDef *config);
void TIM_ITConfig(int timer, int interrupt, int enabled);
void NVIC_Init(NVIC_InitTypeDef *config);
void TIM_Cmd(int timer, int enabled);
int TIM_GetITStatus(int timer, int interrupt);
void TIM_ClearITPendingBit(int timer, int interrupt);
#endif
