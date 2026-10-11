#include <assert.h>
#include <stdint.h>
#include <string.h>

#include "menu.h"
#include "usb.h"
#include "motor.h"
#include "tim2.h"
#include "MG90S.h"

u8 Humi, Temp, modeee;
volatile u8 DHT11_DataValid, ADC_DataValid;
uint16_t Lux, Smoke;
u8 Temp_value, Humi_value, LEDFlag, FanFlag;
uint16_t Lux_value, Smoke_value;
u8 Curtain_ON_Flag, Curtain_OFF_Flag, CurtainFlag;

static uint8_t sent[32];
static unsigned int sentLen;
static int timeoutAfter;
static int timeoutFlag;
static unsigned int lastChannel;
static unsigned int lastAction;
static uint8_t currentScene;
static uint8_t commandedDoor;
static unsigned int doorOpenCount;
static unsigned int doorCloseCount;

void USB_ON(u8 num) { lastChannel = num; lastAction = 1; }
void USB_OFF(u8 num) { lastChannel = num; lastAction = 0; }
void USART_SendData(void *port, uint16_t value)
{
    assert(port == USART2);
    assert(sentLen < sizeof(sent));
    sent[sentLen++] = (uint8_t)value;
}
int USART_GetFlagStatus(void *port, uint16_t flag)
{
    assert(port == USART2 && (flag == USART_FLAG_TC || flag == USART_FLAG_TXE));
    return timeoutAfter >= 0 && sentLen >= (unsigned int)timeoutAfter &&
           (timeoutFlag == 0 || flag == timeoutFlag) ? RESET : 1;
}
void __set_FAULTMASK(int mask) { (void)mask; }
void NVIC_SystemReset(void) { }
int32_t gizPutData(uint8_t *buf, uint32_t len) { (void)buf; (void)len; return 0; }
void HomeScene_Apply(uint8_t scene) { currentScene = scene; }
uint8_t HomeScene_GetCurrent(void) { return currentScene; }
void MG90S_Open(void) { commandedDoor = MG90S_COMMAND_OPEN; doorOpenCount++; }
void MG90S_Close(void) { commandedDoor = MG90S_COMMAND_CLOSE; doorCloseCount++; }
uint8_t MG90S_GetCommandedTarget(void) { return commandedDoor; }

#include "../Gizwits/gizwits_product.c"

static int event(uint8_t type, dataPoint_t *incoming)
{
    eventInfo_t info = {0};
    info.num = 1;
    info.event[0] = type;
    return gizwitsEventProcess(&info, (uint8_t *)incoming, sizeof(*incoming));
}

int main(void)
{
    dataPoint_t incoming = {0};
    uint8_t frame[] = {0xFF, 0xFF, 0x01, 0xFF, 0x02};

    timeoutAfter = -1;
    assert(uartWrite(frame, sizeof(frame)) == sizeof(frame));
    assert(sentLen == 6);
    assert(memcmp(sent, "\xFF\xFF\x01\xFF\x55\x02", 6) == 0);
    assert(uartWrite(frame, sizeof(frame)) == sizeof(frame));
    assert(sentLen == 12);
    sentLen = 0;
    timeoutAfter = 1;
    timeoutFlag = USART_FLAG_TXE;
    assert(uartWrite(frame, sizeof(frame)) == -2);
    assert(sentLen == 1);
    sentLen = 0;
    timeoutAfter = 1;
    timeoutFlag = USART_FLAG_TC;
    assert(uartWrite(frame, 1) == -2);
    assert(uartWrite(NULL, 1) == -1);

    currentScene = HOME_SCENE_AWAY;
    incoming.valueSystem_Mode = System_Mode_VALUE1;
    assert(event(EVENT_System_Mode, &incoming) == 0);
    assert(modeee == 1 && currentScene == HOME_SCENE_NORMAL);

    modeee = 0;
    incoming.valueFan = 1;
    assert(event(EVENT_Fan, &incoming) == 0);
    assert(lastChannel == 2 && lastAction == 1);
    incoming.valueFan = 0;
    assert(event(EVENT_Fan, &incoming) == 0);
    assert(lastChannel == 2 && lastAction == 0);

    currentScene = HOME_SCENE_AWAY;
    incoming.valueDoor_Target = Door_Target_VALUE0;
    assert(event(EVENT_Door_Target, &incoming) == 0);
    assert(doorOpenCount == 0 && doorCloseCount == 0);
    assert(currentScene == HOME_SCENE_AWAY);
    incoming.valueDoor_Target = Door_Target_VALUE1;
    assert(event(EVENT_Door_Target, &incoming) == 0);
    assert(doorOpenCount == 1 && commandedDoor == MG90S_COMMAND_OPEN);
    assert(currentScene == HOME_SCENE_NORMAL);
    incoming.valueDoor_Target = Door_Target_VALUE2;
    assert(event(EVENT_Door_Target, &incoming) == 0);
    assert(doorCloseCount == 1 && commandedDoor == MG90S_COMMAND_CLOSE);
    incoming.valueDoor_Target = Door_Target_VALUE_MAX;
    assert(event(EVENT_Door_Target, &incoming) == -1);
    assert(doorOpenCount == 1 && doorCloseCount == 1);

    incoming.valueHome_Scene = Home_Scene_VALUE1;
    assert(event(EVENT_Home_Scene, &incoming) == 0);
    assert(currentScene == HOME_SCENE_SLEEP);
    incoming.valueHome_Scene = Home_Scene_VALUE2;
    assert(event(EVENT_Home_Scene, &incoming) == 0);
    assert(currentScene == HOME_SCENE_AWAY);
    incoming.valueLight = 1;
    assert(event(EVENT_Light, &incoming) == 0);
    assert(currentScene == HOME_SCENE_NORMAL);
    incoming.valueHome_Scene = Home_Scene_VALUE0;
    assert(event(EVENT_Home_Scene, &incoming) == 0);
    assert(currentScene == HOME_SCENE_NORMAL);
    incoming.valueHome_Scene = Home_Scene_VALUE_MAX;
    assert(event(EVENT_Home_Scene, &incoming) == -1);
    assert(currentScene == HOME_SCENE_NORMAL);
    incoming.valueCurtain = 1;
    assert(event(EVENT_Curtain, &incoming) == 0);
    assert(Curtain_ON_Flag == 1);
    incoming.valueCurtain = 0;
    assert(event(EVENT_Curtain, &incoming) == 0);
    assert(Curtain_OFF_Flag == 1);
    modeee = 1;
    Curtain_ON_Flag = 0;
    incoming.valueCurtain = 1;
    assert(event(EVENT_Curtain, &incoming) == 0);
    assert(Curtain_ON_Flag == 0);

    Temp_value = 40;
    Humi_value = 80;
    Lux_value = 100;
    Smoke_value = 200;
    incoming.valueset_humi = 90;
    assert(event(EVENT_set_humi, &incoming) == 0);
    assert(Humi_value == 90 && Temp_value == 40);
    incoming.valueset_light = 2000;
    assert(event(EVENT_set_light, &incoming) == 0);
    assert(Lux_value == 2000);
    incoming.valueSmoke_Threshold = 2001;
    assert(event(EVENT_Smoke_Threshold, &incoming) == -1);
    assert(Smoke_value == 200);
    incoming.valueSmoke_Threshold = 2000;
    assert(event(EVENT_Smoke_Threshold, &incoming) == 0);
    assert(Smoke_value == 2000);
    userHandle();
    assert(currentDataPoint.valueset_temp == 40);
    assert(currentDataPoint.valueset_humi == 90);
    assert(currentDataPoint.valueset_light == 2000);
    assert(currentDataPoint.valueSmoke_Threshold == 2000);
    assert(currentDataPoint.valueDoor_Target == MG90S_COMMAND_CLOSE);
    assert(currentDataPoint.valueHome_Scene == HOME_SCENE_NORMAL);
    Temp = 25;
    Humi = 50;
    Lux = 300;
    Smoke = 400;
    DHT11_DataValid = 1;
    ADC_DataValid = 1;
    userHandle();
    assert(currentDataPoint.valuetemp == 25 && currentDataPoint.valuehumi == 50);
    assert(currentDataPoint.valueLight_intensity == 300 && currentDataPoint.valueSmmmoke == 400);
    Temp = 0;
    Humi = 0;
    Lux = 0;
    Smoke = 0;
    DHT11_DataValid = 0;
    ADC_DataValid = 0;
    userHandle();
    assert(currentDataPoint.valuetemp == 25 && currentDataPoint.valuehumi == 50);
    assert(currentDataPoint.valueLight_intensity == 300 && currentDataPoint.valueSmmmoke == 400);
    return 0;
}
