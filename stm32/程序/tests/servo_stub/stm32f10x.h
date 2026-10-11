#ifndef SERVO_TEST_STM32F10X_H
#define SERVO_TEST_STM32F10X_H
#include <stdint.h>
typedef struct { uint32_t CFGR; } RCC_TypeDef;
typedef struct { int unused; } GPIO_TypeDef;
typedef struct { int unused; } TIM_TypeDef;
typedef struct { uint32_t GPIO_Pin, GPIO_Speed, GPIO_Mode; } GPIO_InitTypeDef;
typedef struct {
    uint16_t TIM_Prescaler, TIM_Period, TIM_ClockDivision, TIM_CounterMode;
} TIM_TimeBaseInitTypeDef;
typedef struct {
    uint16_t TIM_OCMode, TIM_OutputState, TIM_Pulse, TIM_OCPolarity;
} TIM_OCInitTypeDef;
extern RCC_TypeDef servo_test_rcc;
extern GPIO_TypeDef servo_test_gpio;
extern TIM_TypeDef servo_test_tim;
#define RCC (&servo_test_rcc)
#define GPIOA (&servo_test_gpio)
#define TIM2 (&servo_test_tim)
#define ENABLE 1
#define DISABLE 0
#define RCC_APB2Periph_GPIOA 0x04u
#define RCC_APB1Periph_TIM2 0x01u
#define RCC_CFGR_PPRE1 0x0700u
#define RCC_CFGR_PPRE1_DIV2 0x0400u
#define GPIO_Pin_0 0x01u
#define GPIO_Speed_50MHz 3u
#define GPIO_Mode_Out_PP 0x10u
#define GPIO_Mode_AF_PP 0x18u
#define TIM_Channel_1 0u
#define TIM_CCx_Disable 0u
#define TIM_CCx_Enable 1u
#define TIM_EventSource_Update 1u
#define TIM_FLAG_Update 1u
#define TIM_CKD_DIV1 0u
#define TIM_CounterMode_Up 0u
#define TIM_OCMode_PWM1 0x60u
#define TIM_OutputState_Enable 1u
#define TIM_OCPolarity_High 0u
#define TIM_OCPreload_Enable 1u
void RCC_APB2PeriphClockCmd(uint32_t clock, int enabled);
void RCC_APB1PeriphClockCmd(uint32_t clock, int enabled);
void GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *config);
void GPIO_ResetBits(GPIO_TypeDef *port, uint16_t pins);
void TIM_DeInit(TIM_TypeDef *timer);
void TIM_TimeBaseStructInit(TIM_TimeBaseInitTypeDef *config);
void TIM_TimeBaseInit(TIM_TypeDef *timer, TIM_TimeBaseInitTypeDef *config);
void TIM_OCStructInit(TIM_OCInitTypeDef *config);
void TIM_OC1Init(TIM_TypeDef *timer, TIM_OCInitTypeDef *config);
void TIM_OC1PreloadConfig(TIM_TypeDef *timer, uint16_t enabled);
void TIM_ARRPreloadConfig(TIM_TypeDef *timer, int enabled);
void TIM_CCxCmd(TIM_TypeDef *timer, uint16_t channel, uint16_t enabled);
void TIM_Cmd(TIM_TypeDef *timer, int enabled);
void TIM_SetCompare1(TIM_TypeDef *timer, uint16_t compare);
void TIM_SetCounter(TIM_TypeDef *timer, uint16_t counter);
void TIM_GenerateEvent(TIM_TypeDef *timer, uint16_t event);
void TIM_ClearFlag(TIM_TypeDef *timer, uint16_t flag);
uint16_t TIM_GetCounter(TIM_TypeDef *timer);
uint32_t __get_PRIMASK(void);
void __disable_irq(void);
void __set_PRIMASK(uint32_t value);
#endif
