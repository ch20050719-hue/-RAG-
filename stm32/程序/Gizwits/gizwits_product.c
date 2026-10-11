/**
************************************************************
* @file         gizwits_product.c
* @brief        Gizwits control protocol processing, and platform-related hardware initialization 
* @author       Gizwits
* @date         2017-07-19
* @version      V03030000
* @copyright    Gizwits
*
* @note         Gizwits is only for smart hardware
*               Gizwits Smart Cloud for Smart Products
*               Links | Value Added | Open | Neutral | Safety | Own | Free | Ecology
*               www.gizwits.com
*
***********************************************************/
#include <stdio.h>
#include <string.h>
#include "gizwits_product.h"

#include "common.h"
#include "menu.h"
#include "usb.h"
#include "motor.h"
#include "menu.h"
#include "buzzer.h"
#include "tim2.h"                  // Device header
#include "MG90S.h"
static volatile uint32_t timerMsCount;
#define UART_TX_WAIT_LIMIT 100000u

static int32_t uartWaitFlag(uint16_t flag)
{
    uint32_t waitCount;

    for(waitCount = 0; waitCount < UART_TX_WAIT_LIMIT; waitCount++)
    {
        if(USART_GetFlagStatus(USART2, flag) != RESET)
            return 0;
    }
    return -2;
}

static int32_t uartSendByte(uint8_t value)
{
    if(uartWaitFlag(USART_FLAG_TXE) < 0)
        return -2;
    USART_SendData(USART2, value);
    return 0;
}

/** Current datapoint */
dataPoint_t currentDataPoint;

extern    u8 Curtain_OFF_Flag;
extern    u8 Curtain_ON_Flag;
/**@} */
/**@name Gizwits User Interface
* @{
*/

/**
* @brief Event handling interface

* Description:

* 1. Users can customize the changes in WiFi module status

* 2. Users can add data points in the function of event processing logic, such as calling the relevant hardware peripherals operating interface

* @param [in] info: event queue
* @param [in] data: protocol data
* @param [in] len: protocol data length
* @return NULL
* @ref gizwits_protocol.h
*/
int8_t gizwitsEventProcess(eventInfo_t *info, uint8_t *gizdata, uint32_t len)
{
    uint8_t i = 0;
    dataPoint_t *dataPointPtr = (dataPoint_t *)gizdata;
    moduleStatusInfo_t *wifiData = (moduleStatusInfo_t *)gizdata;
    protocolTime_t *ptime = (protocolTime_t *)gizdata;
    
#if MODULE_TYPE
    gprsInfo_t *gprsInfoData = (gprsInfo_t *)gizdata;
#else
    moduleInfo_t *ptModuleInfo = (moduleInfo_t *)gizdata;
#endif

    if((NULL == info) || (NULL == gizdata))
			
    {
        return -1;
    }

    for(i=0; i<info->num; i++)
    {
        switch(info->event[i])
        {
            case EVENT_Light:
            currentDataPoint.valueLight = dataPointPtr->valueLight;
            GIZWITS_LOG("Evt: EVENT_Light %d \n", currentDataPoint.valueLight);
            if(0x01 == currentDataPoint.valueLight)
            {
                if(modeee==0)
                {
                    HomeScene_Apply(HOME_SCENE_NORMAL);
                    USB_ON(1);
                }
            //user handle
            }
            else
            {
                if(modeee==0)
                {
                    HomeScene_Apply(HOME_SCENE_NORMAL);
                    USB_OFF(1);
                }
            //user handle    
            }
            break;
        case EVENT_Fan:
            currentDataPoint.valueFan = dataPointPtr->valueFan;
            GIZWITS_LOG("Evt: EVENT_Fan %d \n", currentDataPoint.valueFan);
            if(0x01 == currentDataPoint.valueFan)
            {
                if(modeee==0)
                {
                    HomeScene_Apply(HOME_SCENE_NORMAL);
                    USB_ON(2);
                }
                    
            //user handle
            }
            else
            {
                if(modeee==0)
                {
                    HomeScene_Apply(HOME_SCENE_NORMAL);
                    USB_OFF(2);
                }
            //user handle    
            }
            break;
        case EVENT_Curtain:
            currentDataPoint.valueCurtain = dataPointPtr->valueCurtain;
            GIZWITS_LOG("Evt: EVENT_Curtain %d \n", currentDataPoint.valueCurtain);
            if(0x01 == currentDataPoint.valueCurtain)
            {
                if(modeee==0)
                {
                    HomeScene_Apply(HOME_SCENE_NORMAL);
                    Curtain_ON_Flag = 1;
                }
            //user handle
            }
            else
            {
                if(modeee==0)
                {
                    HomeScene_Apply(HOME_SCENE_NORMAL);
                    Curtain_OFF_Flag = 1;
                }
            //user handle    
            }
            break;

        case EVENT_Door_Target:
            if(dataPointPtr->valueDoor_Target >= Door_Target_VALUE_MAX)
                return -1;
            if(dataPointPtr->valueDoor_Target == Door_Target_VALUE1)
            {
                HomeScene_Apply(HOME_SCENE_NORMAL);
                MG90S_Open();
            }
            else if(dataPointPtr->valueDoor_Target == Door_Target_VALUE2)
            {
                HomeScene_Apply(HOME_SCENE_NORMAL);
                MG90S_Close();
            }
            currentDataPoint.valueDoor_Target = MG90S_GetCommandedTarget();
            break;

        case EVENT_Home_Scene:
            if(dataPointPtr->valueHome_Scene >= Home_Scene_VALUE_MAX)
                return -1;
            HomeScene_Apply((uint8_t)dataPointPtr->valueHome_Scene);
            currentDataPoint.valueHome_Scene = HomeScene_GetCurrent();
            break;

        case EVENT_System_Mode:
            currentDataPoint.valueSystem_Mode = dataPointPtr->valueSystem_Mode;
            GIZWITS_LOG("Evt: EVENT_System_Mode %d\n", currentDataPoint.valueSystem_Mode);
            switch(currentDataPoint.valueSystem_Mode)
            {
            case System_Mode_VALUE0://手动
                modeee=0;
                //user handle
                break;
            case System_Mode_VALUE1://自动
                HomeScene_Apply(HOME_SCENE_NORMAL);
                modeee=1;
                //user handle
                break;
            default:
                break;
            }
            break;

        case EVENT_set_temp:
            if(dataPointPtr->valueset_temp > set_temp_MAX)
                return -1;
            Temp_value = (u8)dataPointPtr->valueset_temp;
            currentDataPoint.valueset_temp = Temp_value;
            GIZWITS_LOG("Evt:EVENT_set_temp %d\n", Temp_value);
            //user handle
            break;
        case EVENT_set_humi:
            if(dataPointPtr->valueset_humi > set_humi_MAX)
                return -1;
            Humi_value = (u8)dataPointPtr->valueset_humi;
            currentDataPoint.valueset_humi = Humi_value;
            GIZWITS_LOG("Evt:EVENT_set_humi %d\n", Humi_value);
            //user handle
            break;
        case EVENT_set_light:
            if(dataPointPtr->valueset_light > set_light_MAX * set_light_RATIO)
                return -1;
            Lux_value = (uint16_t)dataPointPtr->valueset_light;
            currentDataPoint.valueset_light = Lux_value;
            GIZWITS_LOG("Evt:EVENT_set_light %d\n", Lux_value);
            //user handle
            break;        
        
        
        case EVENT_Smoke_Threshold:
            if(dataPointPtr->valueSmoke_Threshold > Smoke_Threshold_MAX * Smoke_Threshold_RATIO)
                return -1;
            Smoke_value = (uint16_t)dataPointPtr->valueSmoke_Threshold;
            currentDataPoint.valueSmoke_Threshold = Smoke_value;
            GIZWITS_LOG("Evt:EVENT_Smoke_Threshold %d\n", Smoke_value);
            //user handle
            break;


        case WIFI_SOFTAP:
            break;
        case WIFI_AIRLINK:
            break;
        case WIFI_STATION:
            break;
        case WIFI_CON_ROUTER:
 
            break;
        case WIFI_DISCON_ROUTER:
 
            break;
        case WIFI_CON_M2M:
 
            break;
        case WIFI_DISCON_M2M:
            break;
        case WIFI_RSSI:
            GIZWITS_LOG("RSSI %d\n", wifiData->rssi);
            break;
        case TRANSPARENT_DATA:
            GIZWITS_LOG("TRANSPARENT_DATA \n");
            //user handle , Fetch data from [data] , size is [len]
            break;
        case WIFI_NTP:
            GIZWITS_LOG("WIFI_NTP : [%d-%d-%d %02d:%02d:%02d][%d] \n",ptime->year,ptime->month,ptime->day,ptime->hour,ptime->minute,ptime->second,ptime->ntp);
            break;
        case MODULE_INFO:
            GIZWITS_LOG("MODULE INFO ...\n");
#if MODULE_TYPE
            GIZWITS_LOG("GPRS MODULE ...\n");
            //Format By gprsInfo_t
            GIZWITS_LOG("moduleType : [%d] \n",gprsInfoData->Type);
#else
            GIZWITS_LOG("WIF MODULE ...\n");
            //Format By moduleInfo_t
            GIZWITS_LOG("moduleType : [%d] \n",ptModuleInfo->moduleType);
#endif
        break;
        default:
            break;
        }
    }

    return 0;
}

/**
* User data acquisition

* Here users need to achieve in addition to data points other than the collection of data collection, can be self-defined acquisition frequency and design data filtering algorithm

* @param none
* @return none
*/
void userHandle(void)
{
    
//        if(modeee==1)

    currentDataPoint.valueLight = LEDFlag;
    currentDataPoint.valueFan =FanFlag ;
    currentDataPoint.valueCurtain =CurtainFlag ;
    currentDataPoint.valueSystem_Mode=modeee;
    currentDataPoint.valueDoor_Target = MG90S_GetCommandedTarget();
    currentDataPoint.valueHome_Scene = HomeScene_GetCurrent();
    
    
    //currentDataPoint.valueSystem_Status = ;
    //currentDataPoint.valueSystem_Mode =modeee ;
    if(DHT11_DataValid)
    {
        currentDataPoint.valuetemp = Temp;
        currentDataPoint.valuehumi = Humi;
    }
    currentDataPoint.valueset_temp = Temp_value;
    currentDataPoint.valueset_humi = Humi_value;
    if(ADC_DataValid)
    {
        currentDataPoint.valueLight_intensity = Lux;
        currentDataPoint.valueSmmmoke = Smoke;
    }
    currentDataPoint.valueset_light = Lux_value;
    currentDataPoint.valueSmoke_Threshold = Smoke_value;

 /*
    currentDataPoint.valueSystem_Status = ;//Add Sensor Data Collection
    currentDataPoint.valuetemp = ;//Add Sensor Data Collection
    currentDataPoint.valuehumi = ;//Add Sensor Data Collection
    currentDataPoint.valueLight_intensity = ;//Add Sensor Data Collection
    currentDataPoint.valueSmmmoke = ;//Add Sensor Data Collection

    */
    
}

/**
* Data point initialization function

* In the function to complete the initial user-related data
* @param none
* @return none
* @note The developer can add a data point state initialization value within this function
*/
void userInit(void)
{
    memset((uint8_t*)&currentDataPoint, 0, sizeof(dataPoint_t));
    
    /** Warning !!! DataPoint Variables Init , Must Within The Data Range **/ 
    /*
    currentDataPoint.valueLight = ;
    currentDataPoint.valueFan = ;
    currentDataPoint.valueCurtain = ;
    currentDataPoint.valueSystem_Status = ;
    currentDataPoint.valueSystem_Mode = ;
    currentDataPoint.valuetemp = ;
    currentDataPoint.valuehumi = ;
    currentDataPoint.valueset_temp = ;
    currentDataPoint.valueset_humi = ;
    currentDataPoint.valueset_light = ;
    currentDataPoint.valueSmoke_Threshold = ;
    currentDataPoint.valueLight_intensity = ;
    currentDataPoint.valueSmmmoke = ;
    */

}


/**
* @brief  gizTimerMs

* millisecond timer maintenance function ,Millisecond increment , Overflow to zero

* @param none
* @return none
*/
void gizTimerMs(void)
{
    timerMsCount++;
}

/**
* @brief gizGetTimerCount

* Read system time, millisecond timer

* @param none
* @return System time millisecond
*/
uint32_t gizGetTimerCount(void)
{
    return timerMsCount;
}

/**
* @brief mcuRestart

* MCU Reset function

* @param none
* @return none
*/
void mcuRestart(void)
{
    __set_FAULTMASK(1);
//    HAL_NVIC_SystemReset();
	NVIC_SystemReset();
}
/**@} */

/**
* @brief TIMER_IRQ_FUN

* Timer Interrupt handler function

* @param none
* @return none
*/
void TIMER_IRQ_FUN(void)
{
  gizTimerMs();
}

/**
* @brief UART_IRQ_FUN

* UART Serial interrupt function ，For Module communication

* Used to receive serial port protocol data between WiFi module

* @param none
* @return none
*/
void UART_IRQ_FUN(void)
{
  uint8_t value = 0;
  //value = USART_ReceiveData(USART2);//STM32 test demo
  gizPutData(&value, 1);
}


/**
* @brief uartWrite

* Serial write operation, send data to the WiFi module

* @param buf      : Data address
* @param len       : Data length
*
* @return : Number of source bytes sent, or -1 for invalid input,
*           -2 for a UART transmit timeout.
*/
int32_t uartWrite(uint8_t *buf, uint32_t len)
{
    uint32_t i = 0;
    
    if(NULL == buf)
    {
        return -1;
    }
    
    #ifdef PROTOCOL_DEBUG
    GIZWITS_LOG("MCU2WiFi[%4d:%4d]: ", gizGetTimerCount(), len);
    for(i=0; i<len; i++)
    {
        GIZWITS_LOG("%02x ", buf[i]);
    }
    GIZWITS_LOG("\n");
    #endif

    for(i=0; i<len; i++)
    {
        if(uartSendByte(buf[i]) < 0)
            return -2;
        /* The first two FF bytes are the frame header, not escaped data. */
        if(i >= 2 && buf[i] == 0xFF)
        {
            if(uartSendByte(0x55) < 0)
                return -2;
        }
    }
    if(len > 0 && uartWaitFlag(USART_FLAG_TC) < 0)
        return -2;
    return len;
}
