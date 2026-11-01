#ifndef DOOR_BOARD_H
#define DOOR_BOARD_H
#include <stdint.h>
/* TowerPro MG90S bench endpoints; calibrate with the linkage detached. */
#define SERVO_MIN_US 1000u
#define SERVO_CENTER_US 1500u
#define SERVO_MAX_US 2000u
#define SERVO_OPEN_US 1600u
#define SERVO_CLOSE_US 1400u
#if SERVO_MIN_US < 1000u || SERVO_MAX_US > 2000u || SERVO_MIN_US >= SERVO_MAX_US
#error MG90S pulse envelope must remain within 1000..2000 us
#endif
#if SERVO_CENTER_US < SERVO_MIN_US || SERVO_CENTER_US > SERVO_MAX_US
#error Servo center must be inside the configured pulse envelope
#endif
#if SERVO_OPEN_US < SERVO_MIN_US || SERVO_OPEN_US > SERVO_MAX_US || \
    SERVO_CLOSE_US < SERVO_MIN_US || SERVO_CLOSE_US > SERVO_MAX_US || \
    SERVO_OPEN_US == SERVO_CLOSE_US
#error Calibrated endpoints must be distinct and inside the pulse envelope
#endif
#define REG32(address) (*(volatile uint32_t *)(address))
#define RCC_CR REG32(0x40021000u)
#define RCC_CFGR REG32(0x40021004u)
#define RCC_APB2ENR REG32(0x40021018u)
#define RCC_APB1ENR REG32(0x4002101Cu)
#define GPIOA_CRL REG32(0x40010800u)
#define GPIOA_CRH REG32(0x40010804u)
#define GPIOA_BRR REG32(0x40010814u)
#define TIM2_CR1 REG32(0x40000000u)
#define TIM2_EGR REG32(0x40000014u)
#define TIM2_CCMR1 REG32(0x40000018u)
#define TIM2_CCER REG32(0x40000020u)
#define TIM2_CNT REG32(0x40000024u)
#define TIM2_PSC REG32(0x40000028u)
#define TIM2_ARR REG32(0x4000002Cu)
#define TIM2_CCR1 REG32(0x40000034u)
#define USART1_SR REG32(0x40013800u)
#define USART1_DR REG32(0x40013804u)
#define USART1_BRR REG32(0x40013808u)
#define USART1_CR1 REG32(0x4001380Cu)
void board_init(void);
void board_target(unsigned target);
uint32_t board_millis(void);
void SysTick_Handler(void);
void Default_Handler(void);
#endif
