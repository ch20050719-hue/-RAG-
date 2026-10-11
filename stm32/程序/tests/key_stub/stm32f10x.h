#ifndef KEY_TEST_STM32F10X_H
#define KEY_TEST_STM32F10X_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef struct
{
    uint32_t GPIO_Mode;
    uint32_t GPIO_Pin;
    uint32_t GPIO_Speed;
} GPIO_InitTypeDef;
#define GPIO_Pin_6 (1u << 6)
#define GPIO_Pin_7 (1u << 7)
#define GPIO_Pin_8 (1u << 8)
#define GPIO_Pin_9 (1u << 9)
#define GPIOB ((void *)0x40010c00u)
#define RCC_APB2Periph_GPIOB 8u
#define GPIO_Mode_IPU 1u
#define GPIO_Speed_50MHz 50u
#define ENABLE 1u
void RCC_APB2PeriphClockCmd(uint32_t peripheral, uint32_t enable);
void GPIO_Init(void *port, GPIO_InitTypeDef *config);
int GPIO_ReadInputDataBit(void *port, uint32_t pin);
uint32_t __get_PRIMASK(void);
void __disable_irq(void);
void __set_PRIMASK(uint32_t value);
#endif
