#ifndef STM32F10X_TEST_STUB_H
#define STM32F10X_TEST_STUB_H

#include <stdint.h>

typedef uint8_t u8;
#define GPIO_Pin_3 3u
#define GPIOB ((void *)1)
#define RCC_APB2Periph_AFIO 1u
#define ENABLE 1u
#define GPIO_Remap_SWJ_JTAGDisable 1u
#define GPIO_Speed_50MHz 1u
#define GPIO_Mode_Out_PP 1u
#define GPIO_Mode_IN_FLOATING 2u

typedef struct {
    uint32_t GPIO_Pin;
    uint32_t GPIO_Speed;
    uint32_t GPIO_Mode;
} GPIO_InitTypeDef;

void RCC_APB2PeriphClockCmd(uint32_t peripheral, uint32_t enabled);
void GPIO_PinRemapConfig(uint32_t remap, uint32_t enabled);
void GPIO_Init(void *port, GPIO_InitTypeDef *config);
void GPIO_ResetBits(void *port, uint32_t pin);
void GPIO_SetBits(void *port, uint32_t pin);
int GPIO_ReadInputDataBit(void *port, uint32_t pin);

#endif
