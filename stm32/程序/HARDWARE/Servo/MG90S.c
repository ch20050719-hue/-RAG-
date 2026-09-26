#include "MG90S.h"
#include "MG90S_logic.h"
#include "stm32f10x.h"
#include "system_stm32f10x.h"

#define MG90S_OPEN_PULSE_US 1600u
#define MG90S_CLOSE_PULSE_US 1400u
#define MG90S_MAX_PULSE_US \
    ((MG90S_OPEN_PULSE_US > MG90S_CLOSE_PULSE_US) ? \
        MG90S_OPEN_PULSE_US : MG90S_CLOSE_PULSE_US)

#if MG90S_OPEN_PULSE_US < 1000u || MG90S_OPEN_PULSE_US > 2000u || \
    MG90S_CLOSE_PULSE_US < 1000u || MG90S_CLOSE_PULSE_US > 2000u || \
    MG90S_OPEN_PULSE_US == MG90S_CLOSE_PULSE_US
#error MG90S pulse values must be distinct and within 1000..2000 us
#endif

static MG90S_LogicState servo_state = {0u, MG90S_TARGET_OFF};
static uint8_t servo_clock_valid = 0u;
static uint8_t pwm_active = 0u;
static uint8_t stop_pending = 0u;
static volatile uint8_t commanded_target = MG90S_COMMAND_UNKNOWN;

static void MG90S_PinLow(void)
{
    GPIO_InitTypeDef gpio;

    TIM_CCxCmd(TIM2, TIM_Channel_1, TIM_CCx_Disable);
    TIM_Cmd(TIM2, DISABLE);
    GPIO_ResetBits(GPIOA, GPIO_Pin_0);

    gpio.GPIO_Pin = GPIO_Pin_0;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOA, &gpio);
}

static uint16_t MG90S_PulseForTarget(uint8_t target)
{
    return target == MG90S_TARGET_OPEN ?
        MG90S_OPEN_PULSE_US : MG90S_CLOSE_PULSE_US;
}

static void MG90S_StartPulse(uint8_t target)
{
    GPIO_InitTypeDef gpio;

    MG90S_PinLow();
    TIM_SetCompare1(TIM2, MG90S_PulseForTarget(target));
    TIM_SetCounter(TIM2, 0u);
    TIM_GenerateEvent(TIM2, TIM_EventSource_Update);
    TIM_ClearFlag(TIM2, TIM_FLAG_Update);
    gpio.GPIO_Pin = GPIO_Pin_0;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOA, &gpio);

    TIM_CCxCmd(TIM2, TIM_Channel_1, TIM_CCx_Enable);
    TIM_Cmd(TIM2, ENABLE);
    pwm_active = 1u;
    stop_pending = 0u;
}

static void MG90S_SetTarget(uint8_t target)
{
    if (!servo_clock_valid) {
        return;
    }

    stop_pending = 0u;
    if (!pwm_active) {
        MG90S_StartPulse(target);
        return;
    }

    /* CCR preload applies the new width at the next frame boundary. */
    TIM_SetCompare1(TIM2, MG90S_PulseForTarget(target));
}

static void MG90S_StopAfterPulse(void)
{
    if (pwm_active && TIM_GetCounter(TIM2) >= MG90S_MAX_PULSE_US) {
        MG90S_PinLow();
        pwm_active = 0u;
        stop_pending = 0u;
    }
}

static uint32_t MG90S_EnterCritical(void)
{
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    return primask;
}

static void MG90S_ExitCritical(uint32_t primask)
{
    __set_PRIMASK(primask);
}

static void MG90S_Request(uint8_t target)
{
    uint32_t primask = MG90S_EnterCritical();
    uint8_t previous_target = servo_state.target;

    servo_state = MG90S_Logic_Request(servo_state, target);
    if (servo_state.target != previous_target &&
        servo_state.target != MG90S_TARGET_OFF) {
        MG90S_SetTarget(servo_state.target);
        if (servo_clock_valid) {
            commanded_target = servo_state.target;
        }
    }

    MG90S_ExitCritical(primask);
}

void MG90S_Init(void)
{
    GPIO_InitTypeDef gpio;
    TIM_TimeBaseInitTypeDef timer;
    TIM_OCInitTypeDef channel;

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2, ENABLE);

    GPIO_ResetBits(GPIOA, GPIO_Pin_0);
    gpio.GPIO_Pin = GPIO_Pin_0;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOA, &gpio);

    TIM_DeInit(TIM2);
    TIM_TimeBaseStructInit(&timer);
    timer.TIM_Prescaler = 71u; /* 72 MHz TIM2 clock -> 1 us counter tick. */
    timer.TIM_Period = 19999u; /* 20 ms period -> 50 Hz servo signal. */
    timer.TIM_ClockDivision = TIM_CKD_DIV1;
    timer.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseInit(TIM2, &timer);

    TIM_OCStructInit(&channel);
    channel.TIM_OCMode = TIM_OCMode_PWM1;
    channel.TIM_OutputState = TIM_OutputState_Enable;
    channel.TIM_Pulse = 0u;
    channel.TIM_OCPolarity = TIM_OCPolarity_High;
    TIM_OC1Init(TIM2, &channel);
    TIM_OC1PreloadConfig(TIM2, TIM_OCPreload_Enable);
    TIM_ARRPreloadConfig(TIM2, ENABLE);

    TIM_Cmd(TIM2, DISABLE);
    TIM_CCxCmd(TIM2, TIM_Channel_1, TIM_CCx_Disable);
    TIM_SetCounter(TIM2, 0u);
    TIM_GenerateEvent(TIM2, TIM_EventSource_Update);
    TIM_ClearFlag(TIM2, TIM_FLAG_Update);

    servo_state.target = MG90S_TARGET_OFF;
    servo_state.remaining_ms = 0u;
    pwm_active = 0u;
    stop_pending = 0u;
    commanded_target = MG90S_COMMAND_UNKNOWN;
    servo_clock_valid =
        (SystemCoreClock == 72000000u) &&
        ((RCC->CFGR & RCC_CFGR_PPRE1) == RCC_CFGR_PPRE1_DIV2);
}

void MG90S_Open(void)
{
    MG90S_Request(MG90S_TARGET_OPEN);
}

void MG90S_Close(void)
{
    MG90S_Request(MG90S_TARGET_CLOSE);
}

/* This is the last accepted command, not a measured door position. */
uint8_t MG90S_GetCommandedTarget(void)
{
    return commanded_target;
}

void MG90S_Tick1ms(void)
{
    uint32_t primask = MG90S_EnterCritical();
    uint8_t previous_target = servo_state.target;

    servo_state = MG90S_Logic_Tick(servo_state);
    if (previous_target != MG90S_TARGET_OFF &&
        servo_state.target == MG90S_TARGET_OFF) {
        stop_pending = 1u;
    }
    if (stop_pending) {
        MG90S_StopAfterPulse();
    }

    MG90S_ExitCritical(primask);
}
