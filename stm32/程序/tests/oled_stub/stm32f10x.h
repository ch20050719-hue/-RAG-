#ifndef TEST_OLED_STM32F10X_H
#define TEST_OLED_STM32F10X_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef enum { Bit_RESET = 0, Bit_SET = 1 } BitAction;
typedef struct { uint16_t GPIO_Pin; uint8_t GPIO_Speed; uint8_t GPIO_Mode; } GPIO_InitTypeDef;
#define GPIOB ((void *)2)
#define GPIO_Pin_0 1u
#define GPIO_Pin_1 2u
#define GPIO_Mode_Out_OD 1u
#define GPIO_Speed_50MHz 50u
#define RCC_APB2Periph_GPIOB 1u
#define ENABLE 1u
void GPIO_WriteBit(void *port, uint16_t pin, BitAction value);
void GPIO_Init(void *port, GPIO_InitTypeDef *init);
void RCC_APB2PeriphClockCmd(uint32_t clock, int enable);
#endif
