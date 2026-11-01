#include <assert.h>
#include <stdio.h>
#include "tim2.h"
#include "MG90S.h"

u8 Temp, Humi, Temp_value = 30u, Humi_value = 60u;
uint16_t Lux = 2000u, Smoke, Lux_value = 1000u, Smoke_value = 2000u;
volatile u8 DHT11_DataValid = 1u, ADC_DataValid = 1u;
u8 CurtainFlag, Curtain_ON_Flag, Curtain_OFF_Flag;
static u8 next_command, lamp, fan, buzzer;
static unsigned door_open, door_close, off_calls;
void USB_ON(uint8_t port) { if (port == 1u) lamp = 1u; else fan = 1u; }
void USB_OFF(uint8_t port) { ++off_calls; if (port == 1u) lamp = 0u; else fan = 0u; }
void Buzzer_ON(void) { buzzer = 1u; }
void Buzzer_OFF(void) { buzzer = 0u; }
void MG90S_Open(void) { ++door_open; }
void MG90S_Close(void) { ++door_close; }
uint8_t USART1_TakeCommand(uint8_t *command) {
    *command = next_command; next_command = 0u; return *command != 0u;
}
void Key_scan(void) {}
void RCC_APB2PeriphClockCmd(int c, int e) { (void)c; (void)e; }
void TIM_TimeBaseInit(int t, TIM_TimeBaseInitTypeDef *c) { (void)t; (void)c; }
void TIM_ITConfig(int t, int i, int e) { (void)t; (void)i; (void)e; }
void NVIC_Init(NVIC_InitTypeDef *c) { (void)c; }
void TIM_Cmd(int t, int e) { (void)t; (void)e; }
int TIM_GetITStatus(int t, int i) { (void)t; (void)i; return 0; }
void TIM_ClearITPendingBit(int t, int i) { (void)t; (void)i; }
static void command(u8 value, u8 paused) { next_command = value; HomeControl_Process(paused); }
static void start_auto(void) {
    HomeScene_Apply(HOME_SCENE_AWAY);
    HomeScene_Apply(HOME_SCENE_NORMAL);
    Temp = 40u; Humi = 20u; Lux = 500u; Smoke = 0u;
    DHT11_DataValid = ADC_DataValid = 1u;
    Curtain_ON_Flag = Curtain_OFF_Flag = 0u;
    command(0x08u, 0u);
    assert(lamp && fan && buzzer);
}
static void paused_manual_then_devices(void) {
    start_auto();
    command(0x07u, 1u);
    assert(!lamp && !fan && !buzzer && Curtain_OFF_Flag);
    command(0x01u, 1u);
    command(0x03u, 1u);
    command(0x05u, 1u);
    assert(lamp && fan && Curtain_ON_Flag && !Curtain_OFF_Flag);
    HomeControl_Process(0u);
    assert(lamp && fan && Curtain_ON_Flag && !Curtain_OFF_Flag);
    { unsigned previous = off_calls;
      command(0x07u, 0u);
      assert(lamp && fan && off_calls == previous); }
}
static void external_mode_change_before_action(void) {
    start_auto(); modeee = 0u; command(0x01u, 1u);
    assert(lamp && !fan && !buzzer);
    HomeControl_Process(0u); assert(lamp);
    start_auto(); modeee = 0u; command(0x03u, 0u);
    assert(fan && !lamp && !buzzer);
    start_auto(); modeee = 0u; command(0x05u, 1u);
    assert(Curtain_ON_Flag && !Curtain_OFF_Flag);
}
static void paused_auto_entry_and_scenes(void) {
    start_auto(); command(0x07u, 0u);
    command(0x01u, 1u); command(0x03u, 1u);
    command(0x08u, 1u); assert(lamp && fan);
    command(0x07u, 1u); assert(!lamp && !fan);
    start_auto(); Curtain_ON_Flag = Curtain_OFF_Flag = 0u;
    { unsigned count = door_close;
      command(HOME_SCENE_CMD_SLEEP, 1u);
      assert(!modeee && fan && !lamp && door_close == count + 1u);
      assert(HomeScene_GetCurrent() == HOME_SCENE_SLEEP);
      HomeControl_Process(0u);
      assert(fan && !Curtain_ON_Flag && Curtain_OFF_Flag); }
    start_auto(); Curtain_ON_Flag = Curtain_OFF_Flag = 0u;
    command(HOME_SCENE_CMD_AWAY, 1u); HomeControl_Process(0u);
    assert(!modeee && !fan && !lamp);
    assert(HomeScene_GetCurrent() == HOME_SCENE_AWAY);
    assert(!Curtain_ON_Flag && !Curtain_OFF_Flag);
}
static void preserve_auto_and_single_command_semantics(void) {
    start_auto(); command(0x02u, 1u); assert(modeee && !lamp);
    HomeControl_Process(0u); assert(lamp);
    command(0x07u, 1u);
    Temp = 29u; Humi = 20u; Lux = 2000u;
    command(0x08u, 0u); assert(!fan && !lamp && !buzzer);
    command(MG90S_CMD_OPEN, 1u); assert(modeee && door_open);
    command(0x06u, 1u); assert(Curtain_OFF_Flag && !Curtain_ON_Flag);
}
static void sleep_closes_window(void) {
    unsigned i;
    for (i = 0u; i < 4u; ++i) {
        CurtainFlag = (u8)(i % 2u);
        Curtain_ON_Flag = 1u; Curtain_OFF_Flag = 0u;
        command(HOME_SCENE_CMD_SLEEP, (u8)(i % 2u));
        assert(!Curtain_ON_Flag && Curtain_OFF_Flag);
        command(HOME_SCENE_CMD_SLEEP, 0u);
        assert(!Curtain_ON_Flag && Curtain_OFF_Flag);
    }
}
static void wakeup_after_sleep(void) {
    unsigned opened;
    u8 paused;
    for (paused = 0u; paused <= 1u; ++paused) {
        command(HOME_SCENE_CMD_SLEEP, paused);
        assert(!lamp && fan && !modeee);
        Curtain_ON_Flag = paused;
        Curtain_OFF_Flag = (u8)!paused;
        opened = door_open;
        command(HOME_SCENE_CMD_WAKEUP, paused);
        assert(lamp && !fan && !modeee && door_open == opened + 1u);
        assert(HomeScene_GetCurrent() == HOME_SCENE_NORMAL);
        assert(Curtain_ON_Flag == paused && Curtain_OFF_Flag == (u8)!paused);
        HomeControl_Process(0u);
        assert(lamp && !fan && door_open == opened + 1u);
    }
    /* Normal/manual are still mode changes, not implicit wakeup actions. */
    command(HOME_SCENE_CMD_SLEEP, 0u);
    opened = door_open;
    HomeScene_Apply(HOME_SCENE_NORMAL);
    command(0x07u, 0u);
    assert(!lamp && fan && door_open == opened);
    start_auto();
    command(HOME_SCENE_CMD_WAKEUP, 1u);
    assert(lamp && !fan && !modeee && !buzzer);
    HomeControl_Process(0u);
    assert(lamp && !fan);
    command(HOME_SCENE_CMD_AWAY, 0u);
    Curtain_ON_Flag = Curtain_OFF_Flag = 0u;
    command(HOME_SCENE_CMD_WAKEUP, 0u);
    assert(lamp && !fan && !Curtain_ON_Flag && !Curtain_OFF_Flag);
    opened = door_open;
    command(HOME_SCENE_CMD_WAKEUP, 0u);
    assert(lamp && !fan && door_open == opened + 1u);
    opened = door_open;
    command(0x0Eu, 0u);
    assert(lamp && !fan && door_open == opened);
}
int main(void) {
    sleep_closes_window();
    wakeup_after_sleep();
    paused_manual_then_devices();
    external_mode_change_before_action();
    paused_auto_entry_and_scenes();
    preserve_auto_and_single_command_semantics();
    puts("home control: all mode ordering regressions passed");
    return 0;
}
