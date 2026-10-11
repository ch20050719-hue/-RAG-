#include <assert.h>
#include <stdio.h>
#include "../HARDWARE/Key.h"

static uint32_t pressed;
static uint32_t interrupt_mask;
static uint32_t disabled_count;
static uint32_t configured_pins;

void RCC_APB2PeriphClockCmd(uint32_t peripheral, uint32_t enable)
{
    assert(peripheral == RCC_APB2Periph_GPIOB && enable == ENABLE);
}
void GPIO_Init(void *port, GPIO_InitTypeDef *config)
{
    assert(port == GPIOB && config->GPIO_Mode == GPIO_Mode_IPU);
    configured_pins |= config->GPIO_Pin;
}
int GPIO_ReadInputDataBit(void *port, uint32_t pin)
{
    assert(port == GPIOB);
    return (pressed & pin) == 0;
}
uint32_t __get_PRIMASK(void) { return interrupt_mask; }
void __disable_irq(void) { interrupt_mask = 1; ++disabled_count; }
void __set_PRIMASK(uint32_t value)
{
    assert(interrupt_mask == 1);
    interrupt_mask = value;
}

int main(void)
{
    unsigned int tick;
    u8 current;
    Key_Init();
    assert(configured_pins == (GPIO_Pin_6 | GPIO_Pin_7 | GPIO_Pin_8 | GPIO_Pin_9));
    assert(Key_TakeEvent() == 0 && interrupt_mask == 0);
    interrupt_mask = 1;
    assert(Key_TakeEvent() == 0 && interrupt_mask == 1);
    interrupt_mask = 0;
    pressed = GPIO_Pin_6 | GPIO_Pin_7 | GPIO_Pin_8 | GPIO_Pin_9;
    for (tick = 0; tick < KEY_DELAY_TIME; ++tick)
        Key_scan();
    assert(Key_TakeEvent() == 0);
    Key_scan();
    current = Key_TakeEvent();
    assert(current == 1);
    /* Foreground clearing its current key cannot erase queued keys. */
    current = 0;
    assert(current == 0 && Key_TakeEvent() == 2);
    assert(Key_TakeEvent() == 3);
    assert(Key_TakeEvent() == 4);
    assert(Key_TakeEvent() == 0);
    pressed = 0;
    Key_scan();
    assert(Key_TakeEvent() == 0);
    pressed = GPIO_Pin_9;
    /* Let repeats fill the queue, then release the network setup key. */
    for (tick = 0; tick < KEY_DELAY_TIME + KEY_LONG_TIME + 20u; ++tick)
        Key_scan();
    pressed = 0;
    Key_scan();
    for (tick = 0; tick < 7u; ++tick)
        assert(Key_TakeEvent() == 4);
    assert(Key_TakeEvent() == 44);
    assert(Key_TakeEvent() == 0);
    assert(disabled_count > 0 && interrupt_mask == 0);
    puts("key scan integration tests passed");
    return 0;
}
