#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "stm32f10x.h"
#include "MG90S.h"
#include "MG90S_logic.h"
#include "MG90S_calibration.h"

#define EXPECTED_OPEN_US 1000u
#define EXPECTED_CLOSE_US 1600u

RCC_TypeDef servo_test_rcc;
GPIO_TypeDef servo_test_gpio;
TIM_TypeDef servo_test_tim;
uint32_t SystemCoreClock;

typedef struct {
    TIM_TimeBaseInitTypeDef base;
    TIM_OCInitTypeDef channel;
    uint32_t gpio_mode, apb1, apb2, primask;
    uint16_t counter, active_compare, shadow_compare;
    unsigned writes, updates, completed_pulses, truncated_pulses;
    int running, channel_enabled, preload, arr_preload, gpio_low;
} TimerModel;

static TimerModel model;
static unsigned checks;
#define CHECK(expression) do { ++checks; if (!(expression)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #expression); exit(1); \
} } while (0)

static int output_high(void)
{
    return model.running && model.channel_enabled &&
        model.gpio_mode == GPIO_Mode_AF_PP && model.counter < model.active_compare;
}

static void advance_us(unsigned elapsed)
{
    while (elapsed-- > 0u) {
        if (!model.running) { continue; }
        ++model.counter;
        if (model.counter == model.active_compare && model.channel_enabled) {
            ++model.completed_pulses;
        }
        if (model.counter > model.base.TIM_Period) {
            model.counter = 0u;
            model.active_compare = model.shadow_compare;
            ++model.updates;
        }
    }
}

static void tick_ms(unsigned elapsed)
{
    while (elapsed-- > 0u) {
        advance_us(1000u);
        MG90S_Tick1ms();
    }
}

static void reset_driver(uint32_t core_clock, uint32_t divider)
{
    memset(&model, 0, sizeof(model));
    SystemCoreClock = core_clock;
    servo_test_rcc.CFGR = divider;
    MG90S_Init();
}

void RCC_APB2PeriphClockCmd(uint32_t clock, int enabled)
{ if (enabled) { model.apb2 |= clock; } }
void RCC_APB1PeriphClockCmd(uint32_t clock, int enabled)
{ if (enabled) { model.apb1 |= clock; } }
void GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *config)
{
    CHECK(port == GPIOA && config->GPIO_Pin == GPIO_Pin_0);
    CHECK(config->GPIO_Speed == GPIO_Speed_50MHz);
    model.gpio_mode = config->GPIO_Mode;
}
void GPIO_ResetBits(GPIO_TypeDef *port, uint16_t pins)
{ CHECK(port == GPIOA && pins == GPIO_Pin_0); model.gpio_low = 1; }
void TIM_DeInit(TIM_TypeDef *timer)
{
    CHECK(timer == TIM2);
    model.running = 0; model.channel_enabled = 0;
    model.active_compare = 0u; model.shadow_compare = 0u;
}
void TIM_TimeBaseStructInit(TIM_TimeBaseInitTypeDef *config)
{ memset(config, 0, sizeof(*config)); }
void TIM_TimeBaseInit(TIM_TypeDef *timer, TIM_TimeBaseInitTypeDef *config)
{ CHECK(timer == TIM2); model.base = *config; }
void TIM_OCStructInit(TIM_OCInitTypeDef *config)
{ memset(config, 0, sizeof(*config)); }
void TIM_OC1Init(TIM_TypeDef *timer, TIM_OCInitTypeDef *config)
{
    CHECK(timer == TIM2); model.channel = *config;
    model.active_compare = config->TIM_Pulse;
    model.shadow_compare = config->TIM_Pulse;
}
void TIM_OC1PreloadConfig(TIM_TypeDef *timer, uint16_t enabled)
{ CHECK(timer == TIM2); model.preload = enabled == TIM_OCPreload_Enable; }
void TIM_ARRPreloadConfig(TIM_TypeDef *timer, int enabled)
{ CHECK(timer == TIM2); model.arr_preload = enabled; }
void TIM_CCxCmd(TIM_TypeDef *timer, uint16_t channel, uint16_t enabled)
{
    CHECK(timer == TIM2 && channel == TIM_Channel_1);
    if (enabled == TIM_CCx_Disable && output_high()) { ++model.truncated_pulses; }
    model.channel_enabled = enabled == TIM_CCx_Enable;
}
void TIM_Cmd(TIM_TypeDef *timer, int enabled)
{
    CHECK(timer == TIM2);
    if (!enabled && output_high()) { ++model.truncated_pulses; }
    model.running = enabled;
}
void TIM_SetCompare1(TIM_TypeDef *timer, uint16_t compare)
{
    CHECK(timer == TIM2); ++model.writes;
    model.shadow_compare = compare;
    if (!model.preload) { model.active_compare = compare; }
}
void TIM_SetCounter(TIM_TypeDef *timer, uint16_t counter)
{ CHECK(timer == TIM2); model.counter = counter; }
void TIM_GenerateEvent(TIM_TypeDef *timer, uint16_t event)
{
    CHECK(timer == TIM2 && event == TIM_EventSource_Update);
    model.active_compare = model.shadow_compare; ++model.updates;
}
void TIM_ClearFlag(TIM_TypeDef *timer, uint16_t flag)
{ CHECK(timer == TIM2 && flag == TIM_FLAG_Update); }
uint16_t TIM_GetCounter(TIM_TypeDef *timer)
{ CHECK(timer == TIM2); return model.counter; }
uint32_t __get_PRIMASK(void) { return model.primask; }
void __disable_irq(void) { model.primask = 1u; }
void __set_PRIMASK(uint32_t value) { model.primask = value; }

static void test_init_and_frame_switch(void)
{
    unsigned updates;
    reset_driver(72000000u, RCC_CFGR_PPRE1_DIV2);
    CHECK(model.apb1 == RCC_APB1Periph_TIM2);
    CHECK(model.apb2 == RCC_APB2Periph_GPIOA);
    CHECK(model.base.TIM_Prescaler == 71u && model.base.TIM_Period == 19999u);
    CHECK(model.channel.TIM_OCMode == TIM_OCMode_PWM1);
    CHECK(model.channel.TIM_OCPolarity == TIM_OCPolarity_High);
    CHECK(model.preload && model.arr_preload);
    CHECK(!model.running && !model.channel_enabled && model.gpio_low);
    CHECK(model.gpio_mode == GPIO_Mode_Out_PP);
    CHECK(MG90S_GetCommandedTarget() == MG90S_COMMAND_UNKNOWN);
    advance_us(2000000u);
    CHECK(model.completed_pulses == 0u);
    MG90S_Open();
    CHECK(model.running && model.channel_enabled && output_high());
    CHECK(model.active_compare == EXPECTED_OPEN_US);
    advance_us(500u);
    updates = model.updates;
    MG90S_Close();
    CHECK(model.counter == 500u && model.updates == updates);
    CHECK(model.active_compare == EXPECTED_OPEN_US);
    CHECK(model.shadow_compare == EXPECTED_CLOSE_US);
    CHECK(MG90S_GetCommandedTarget() == MG90S_COMMAND_CLOSE);
    advance_us(19500u);
    CHECK(model.active_compare == EXPECTED_CLOSE_US && model.counter == 0u);
    CHECK(model.truncated_pulses == 0u);
}

static void test_complete_hold_and_retry(void)
{
    unsigned writes;
    reset_driver(72000000u, RCC_CFGR_PPRE1_DIV2);
    MG90S_Close();
    CHECK(model.active_compare == EXPECTED_CLOSE_US);
    tick_ms(MG90S_ACTION_HOLD_MS / 2u);
    writes = model.writes;
    MG90S_Close();
    CHECK(model.writes == writes);
    tick_ms(MG90S_ACTION_HOLD_MS / 2u - 1u);
    CHECK(model.running);
    tick_ms(1u);
    CHECK(model.running && model.counter == 0u);
    tick_ms(1u);
    CHECK(model.running);
    tick_ms(1u);
    CHECK(!model.running && !model.channel_enabled);
    CHECK(model.gpio_mode == GPIO_Mode_Out_PP && model.gpio_low);
    CHECK(model.completed_pulses == MG90S_ACTION_HOLD_MS / 20u + 1u);
    CHECK(model.truncated_pulses == 0u);
    CHECK(MG90S_GetCommandedTarget() == MG90S_COMMAND_CLOSE);
    MG90S_Close();
    CHECK(model.running && model.active_compare == EXPECTED_CLOSE_US);
    CHECK(model.writes == writes + 1u);
}

static void test_pwm_widths_and_period(void)
{
    reset_driver(72000000u, RCC_CFGR_PPRE1_DIV2);
    MG90S_Open();
    advance_us(EXPECTED_OPEN_US - 1u);
    CHECK(output_high());
    advance_us(1u);
    CHECK(!output_high() && model.completed_pulses == 1u);
    advance_us(20000u - EXPECTED_OPEN_US - 1u);
    CHECK(!output_high() && model.counter == 19999u);
    advance_us(1u);
    CHECK(output_high() && model.counter == 0u);
    MG90S_Close();
    CHECK(model.active_compare == EXPECTED_OPEN_US);
    advance_us(20000u);
    CHECK(output_high() && model.active_compare == EXPECTED_CLOSE_US);
    advance_us(EXPECTED_CLOSE_US - 1u);
    CHECK(output_high());
    advance_us(1u);
    CHECK(!output_high() && model.completed_pulses == 3u);
    CHECK(model.truncated_pulses == 0u);
}

static void test_critical_and_invalid_clock(void)
{
    reset_driver(72000000u, RCC_CFGR_PPRE1_DIV2);
    model.primask = 1u;
    MG90S_Open();
    CHECK(model.primask == 1u);
    MG90S_Tick1ms();
    CHECK(model.primask == 1u);
    model.primask = 0u;
    MG90S_Close();
    CHECK(model.primask == 0u);
    MG90S_Tick1ms();
    CHECK(model.primask == 0u);
    reset_driver(36000000u, RCC_CFGR_PPRE1_DIV2);
    MG90S_Open(); MG90S_Close(); tick_ms(MG90S_ACTION_HOLD_MS + 20u);
    CHECK(!model.running && model.writes == 0u);
    CHECK(MG90S_GetCommandedTarget() == MG90S_COMMAND_UNKNOWN);
    reset_driver(72000000u, 0u);
    MG90S_Open(); MG90S_Close();
    CHECK(!model.running && model.writes == 0u);
    CHECK(MG90S_GetCommandedTarget() == MG90S_COMMAND_UNKNOWN);
}

static void test_target_change_renews_hold(void)
{
    reset_driver(72000000u, RCC_CFGR_PPRE1_DIV2);
    MG90S_Open();
    tick_ms(MG90S_ACTION_HOLD_MS - 5u);
    CHECK(model.running);
    MG90S_Close();
    CHECK(model.shadow_compare == EXPECTED_CLOSE_US);
    CHECK(model.active_compare == EXPECTED_OPEN_US);
    tick_ms(5u);
    CHECK(model.running && model.active_compare == EXPECTED_CLOSE_US);
    tick_ms(MG90S_ACTION_HOLD_MS - 6u);
    CHECK(model.running);
    tick_ms(1u);
    CHECK(!model.running && model.gpio_mode == GPIO_Mode_Out_PP);
    CHECK(model.truncated_pulses == 0u);
}

static void test_new_command_during_pending_stop(void)
{
    reset_driver(72000000u, RCC_CFGR_PPRE1_DIV2);
    MG90S_Open();
    tick_ms(MG90S_ACTION_HOLD_MS);
    CHECK(model.running && output_high());
    MG90S_Close();
    CHECK(model.active_compare == EXPECTED_OPEN_US);
    CHECK(model.shadow_compare == EXPECTED_CLOSE_US);
    tick_ms(20u);
    CHECK(model.running && model.active_compare == EXPECTED_CLOSE_US);
    tick_ms(MG90S_ACTION_HOLD_MS - 20u + 2u);
    CHECK(!model.running && !model.channel_enabled);
    CHECK(model.truncated_pulses == 0u);
}

int main(void)
{
    uint32_t calibrated_open = MG90S_OPEN_PULSE_US;
    uint32_t calibrated_close = MG90S_CLOSE_PULSE_US;
    CHECK(calibrated_open == EXPECTED_OPEN_US);
    CHECK(calibrated_close == EXPECTED_CLOSE_US);
    test_init_and_frame_switch();
    test_complete_hold_and_retry();
    test_pwm_widths_and_period();
    test_critical_and_invalid_clock();
    test_target_change_renews_hold();
    test_new_command_during_pending_stop();
    printf("Servo driver: %u dynamic checks passed\n", checks);
    return 0;
}
