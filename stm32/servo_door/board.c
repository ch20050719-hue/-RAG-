#include "board.h"
static volatile uint32_t milliseconds;
static unsigned applied_target;

void SysTick_Handler(void) { ++milliseconds; }
uint32_t board_millis(void) { return milliseconds; }

static void pwm_off(void)
{
    TIM2_CCER = 0;
    TIM2_CR1 = 0;
    GPIOA_BRR = 1;
    GPIOA_CRL = (GPIOA_CRL & ~15u) | 2u; /* PA0 push-pull low */
}

void Default_Handler(void)
{
    RCC_APB2ENR |= 4u;
    RCC_APB1ENR |= 1u;
    pwm_off();
    for (;;) { } /* Fault requires reset; never continue moving. */
}

void board_init(void)
{
    RCC_CR |= 1u;
    while (!(RCC_CR & 2u)) { }
    RCC_CFGR &= ~3u;
    while (RCC_CFGR & 12u) { }
    RCC_CFGR = 0; /* HSI 8 MHz; AHB/APB1/APB2 all /1. */
    RCC_CR &= ~((1u<<24) | (1u<<16));
    RCC_APB2ENR |= (1u<<14) | 4u | 1u;
    RCC_APB1ENR |= 1u;
    pwm_off();
    /* PA9 alternate push-pull 2 MHz; PA10 floating input. */
    GPIOA_CRH = (GPIOA_CRH & ~0xFF0u) | 0x4A0u;
    USART1_CR1 = 0;
    USART1_BRR = 69u; /* 8 MHz / 69 = 115942 baud (+0.64% nominal). */
    USART1_CR1 = (1u<<13) | (1u<<3) | (1u<<2);
    TIM2_PSC = 7u;
    TIM2_ARR = 19999u;
    TIM2_CCMR1 = (6u<<4) | (1u<<3); /* PWM1 + preload */
    REG32(0xE000ED08u) = 0x08000000u; /* VTOR */
    REG32(0xE000E014u) = 7999u;
    REG32(0xE000E018u) = 0;
    REG32(0xE000E010u) = 7u; /* SysTick 1 ms */
}

void board_target(unsigned target)
{
    if (target > 2u) target = 0u;
    if (target == applied_target) return;
    pwm_off();
    if (target != 0) {
        TIM2_CCR1 = target == 1 ? SERVO_OPEN_US : SERVO_CLOSE_US;
        TIM2_CNT = 0;
        TIM2_EGR = 1u;
        GPIOA_CRL = (GPIOA_CRL & ~15u) | 10u;
        TIM2_CCER = 1u;
        TIM2_CR1 = (1u<<7) | 1u;
    }
    applied_target = target;
}
