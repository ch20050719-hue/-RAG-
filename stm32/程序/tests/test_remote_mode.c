/* Exercise the production cloud callback and mode state machine together. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define main home_control_baseline_main
#include "test_home_control.c"
#undef main
/* Console failures also work in a DLL host without a Windows assertion dialog. */
#undef assert
#define assert(test) do { if (!(test)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #test); \
    fflush(stderr); exit(1); } } while (0)

#define USART2 ((void *)2)
#define USART_FLAG_TC 1
#define USART_FLAG_TXE 2
u8 LEDFlag, FanFlag;
void USART_SendData(void *port, uint16_t value) { (void)port; (void)value; }
int USART_GetFlagStatus(void *port, uint16_t flag) { (void)port; (void)flag; return 1; }
void __set_FAULTMASK(int mask) { (void)mask; }
void NVIC_SystemReset(void) { }
int32_t gizPutData(uint8_t *buf, uint32_t len) { (void)buf; (void)len; return 0; }
uint8_t MG90S_GetCommandedTarget(void) { return MG90S_COMMAND_CLOSE; }

#ifndef REMOTE_PRODUCT_SOURCE
#define REMOTE_PRODUCT_SOURCE "../Gizwits/gizwits_product.c"
#endif
#include REMOTE_PRODUCT_SOURCE

static void combined_manual(unsigned mode_position)
{
    eventInfo_t events = {0};
    dataPoint_t data = {0};
    unsigned i, action = 0;
    const uint8_t actions[] = {EVENT_Light, EVENT_Fan, EVENT_Curtain};
    start_auto();
    /* Use OFF before the request so dropped ON actions cannot pass. */
    USB_OFF(1); USB_OFF(2);
    data.valueLight = data.valueFan = data.valueCurtain = 1;
    data.valueSystem_Mode = System_Mode_VALUE0;
    events.num = 4;
    for (i = 0; i < 4; ++i)
        events.event[i] = i == mode_position ? EVENT_System_Mode : actions[action++];
    assert(gizwitsEventProcess(&events, (uint8_t *)&data, sizeof(data)) == 0);
    assert(!modeee && lamp && fan && !buzzer);
    assert(Curtain_ON_Flag && !Curtain_OFF_Flag);
    HomeControl_Process(1u);
    HomeControl_Process(0u);
    assert(!modeee && lamp && fan && !buzzer);
    assert(Curtain_ON_Flag && !Curtain_OFF_Flag);
}

static void manual_only_and_auto(void)
{
    eventInfo_t events = {0};
    dataPoint_t data = {0};
    unsigned previous;
    start_auto();
    events.num = 1;
    events.event[0] = EVENT_System_Mode;
    data.valueSystem_Mode = System_Mode_VALUE0;
    assert(gizwitsEventProcess(&events, (uint8_t *)&data, sizeof(data)) == 0);
    assert(!modeee && !lamp && !fan && !buzzer);
    assert(Curtain_OFF_Flag && !Curtain_ON_Flag);
    USB_ON(1); USB_ON(2);
    previous = off_calls;
    assert(gizwitsEventProcess(&events, (uint8_t *)&data, sizeof(data)) == 0);
    HomeControl_Process(0u);
    assert(lamp && fan && off_calls == previous);
    /* Automatic mode still owns outputs; an accompanying OFF cannot override it. */
    events.num = 4;
    events.event[0] = EVENT_Light;
    events.event[1] = EVENT_Fan;
    events.event[2] = EVENT_Curtain;
    events.event[3] = EVENT_System_Mode;
    data.valueSystem_Mode = System_Mode_VALUE1;
    assert(gizwitsEventProcess(&events, (uint8_t *)&data, sizeof(data)) == 0);
    assert(modeee && lamp && fan);
    HomeControl_Process(0u);
    assert(modeee && lamp && fan && buzzer);
}

static void scene_after_mode(void)
{
    eventInfo_t events = {0};
    dataPoint_t data = {0};
    start_auto();
    events.num = 2;
    events.event[0] = EVENT_System_Mode;
    events.event[1] = EVENT_Home_Scene;
    data.valueSystem_Mode = System_Mode_VALUE1;
    data.valueHome_Scene = Home_Scene_VALUE1;
    assert(gizwitsEventProcess(&events, (uint8_t *)&data, sizeof(data)) == 0);
    assert(!modeee && !lamp && fan && HomeScene_GetCurrent() == HOME_SCENE_SLEEP);
    assert(!Curtain_ON_Flag && Curtain_OFF_Flag);
    HomeControl_Process(0u);
    assert(!modeee && !lamp && fan && HomeScene_GetCurrent() == HOME_SCENE_SLEEP);
    assert(!Curtain_ON_Flag && Curtain_OFF_Flag);
}

int main(void)
{
    unsigned i;
    home_control_baseline_main();
    for (i = 0; i < 4; ++i) combined_manual((i + 3u) % 4u);
    manual_only_and_auto();
    scene_after_mode();
    puts("remote mode: real cloud callback + TIM2 ordering regressions passed");
    return 0;
}
