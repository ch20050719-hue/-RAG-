#include "menu.h"
#include "MG90S.h"
#include "ldr.h"
#include "tim2.h"                  // Device header
#include "usb.h"
#include "motor.h"
#include "adcx.h"
uint16_t Smoke;
u8 Humi,Temp;
uint16_t Lux;	
volatile u8 DHT11_DataValid = 0u;
volatile uint32_t DHT11_LastSuccessMs = 0u;
volatile u8 ADC_DataValid = 0u;
volatile uint32_t ADC_LastSuccessMs = 0u;

/* Sample independent of the selected OLED page. Keep the last good readings on failure. */
void Menu_UpdateSensors(uint32_t now_ms)
{
    u8 humi;
    u8 temp;
    u16 lux_adc;
    u16 smoke_adc;

    if (DHT11_Read_Data(&humi, &temp) == DHT11_READ_OK) {
        DHT11_DataValid = 0u;
        Humi = humi;
        Temp = temp;
        DHT11_LastSuccessMs = now_ms;
        DHT11_DataValid = 1u;
    } else {
        DHT11_DataValid = 0u;
    }

    if (ADCX_ReadValue(0x05, &lux_adc) && ADCX_ReadValue(0x04, &smoke_adc)) {
        ADC_DataValid = 0u;
        Lux = 4096u - lux_adc;
        Smoke = smoke_adc;
        ADC_LastSuccessMs = now_ms;
        ADC_DataValid = 1u;
    } else {
        ADC_DataValid = 0u;
    }
}
u8 aaabbb;
extern    u8 Curtain_OFF_Flag;
extern    u8 Curtain_ON_Flag;

void Menu1(void)
{		
	//显示“温度：  C”
	OLED_ShowChinese(1,1,0);
	OLED_ShowChinese(1,2,1);
	OLED_ShowChar(1,5,':');
	OLED_ShowChar(1,8,'C');
	
	//显示“湿度:   %”
	OLED_ShowChinese(1,5,2);
	OLED_ShowChinese(1,6,3);
	OLED_ShowChar(1,13,':');	
	OLED_ShowChar(1,16,'%');
	
	//显示”光照强度：  Lux“
	OLED_ShowChinese(2, 1, 5);
	OLED_ShowChinese(2, 2, 20);
	OLED_ShowChinese(2, 3, 21);
	OLED_ShowChinese(2, 4, 22);
	OLED_ShowChar(2, 9, ':');
	OLED_ShowString(2, 14, "Lux"); 

	//显示”烟雾浓度：  ADC“
	OLED_ShowChinese(3, 1, 32);
	OLED_ShowChinese(3, 2, 33);
	OLED_ShowChinese(3, 3, 34);
	OLED_ShowChinese(3, 4, 35);
	OLED_ShowChar(3, 9, ':');
	OLED_ShowString(3, 14, "ADC");
    
    
	OLED_ShowChinese(4, 6, 24);
	OLED_ShowChinese(4, 7, 26);
	OLED_ShowChinese(4, 8, 27);
	
	if (DHT11_DataValid) {
        OLED_ShowNum(1,6,Temp,2);
    } else {
        OLED_ShowString(1,6,"--");
    }
	if (DHT11_DataValid) {
        OLED_ShowNum(1,14,Humi,2);
    } else {
        OLED_ShowString(1,14,"--");
    }
	
	//显示光照强度数据
	if (ADC_DataValid) {
        OLED_ShowNum(2, 10, Lux, 4);
    } else {
        OLED_ShowString(2, 10, "----");
    }
	//显示烟雾浓度数据
	if (ADC_DataValid) {
        OLED_ShowNum(3, 10, Smoke, 4);
    } else {
        OLED_ShowString(3, 10, "----");
    }
	
	
	
    	if(!modeee)
	{
		OLED_ShowChinese(4, 5, 23);//手
	}
	else
	{
		OLED_ShowChinese(4, 5, 25);//自
	}

}
void Menu11(void)
{
    
    	//显示“灯光：”
	OLED_ShowChinese(1,1,4);
	OLED_ShowChinese(1,2,5);
	OLED_ShowChar(1,5,':');

	//显示“风扇：”
	OLED_ShowChinese(1,5,6);
	OLED_ShowChinese(1,6,7);
	OLED_ShowChar(1,13,':');
	
	//显示“窗帘：”
	OLED_ShowChinese(2,1,8);
	OLED_ShowChinese(2,2,9);
	OLED_ShowChar(2,5,':');

	if(!LEDFlag)
	{
		OLED_ShowChineseOffset(1, 3, 19);
	}
	else
	{	
		OLED_ShowChineseOffset(1, 3, 18);
	}

	if(!FanFlag)
	{
		OLED_ShowChineseOffset(1, 7, 19);
	}
	else
	{
		OLED_ShowChineseOffset(1, 7, 18);
	}

	if(!CurtainFlag)
	{	
		OLED_ShowChineseOffset(2, 3, 19);
	}
	else
	{
		OLED_ShowChineseOffset(2, 3, 18);
	}
	
    /* Clear the whole row before drawing four 16x16 characters. */
    OLED_ShowString(3, 1, "                ");
    switch (HomeScene_GetCurrent()) {
        case HOME_SCENE_SLEEP:
            OLED_ShowChinese(3, 3, 37); /* sleep */
            OLED_ShowChinese(3, 4, 38);
            break;
        case HOME_SCENE_AWAY:
            OLED_ShowChinese(3, 3, 39); /* away */
            OLED_ShowChinese(3, 4, 40);
            break;
        default:
            OLED_ShowChinese(3, 3, modeee ? 25 : 23);
            OLED_ShowChinese(3, 4, 24);
            break;
    }
    OLED_ShowChinese(3, 5, 26);
    OLED_ShowChinese(3, 6, 27);

    OLED_ShowString(4, 1, "                ");
    switch (MOTOR_GetMotionStatus()) {
        case WINDOW_MOTION_OPENING:
            OLED_ShowChinese(4, 3, 41);
            OLED_ShowChinese(4, 4, 42);
            OLED_ShowChinese(4, 5, 28);
            OLED_ShowChinese(4, 6, 29);
            break;
        case WINDOW_MOTION_CLOSING:
            OLED_ShowChinese(4, 3, 41);
            OLED_ShowChinese(4, 4, 42);
            OLED_ShowChinese(4, 5, 30);
            OLED_ShowChinese(4, 6, 31);
            break;
        default:
            OLED_ShowChinese(4, 4, 43);
            OLED_ShowChinese(4, 5, 44);
            break;
    }
}
void Menu2(void)
{
//	//显示“系统阈值调节：”
//	OLED_ShowChinese(1,1,12);
//	OLED_ShowChinese(1,2,13);
//	OLED_ShowChinese(1,3,14);
//	OLED_ShowChinese(1,4,15);
//	OLED_ShowChinese(1,5,16);
//	OLED_ShowChinese(1,6,17);
//	OLED_ShowChar(1,13,':');
	
//	//显示“温度：”
//	OLED_ShowChinese(2,2,0);
//	OLED_ShowChinese(2,3,1);
//	OLED_ShowChar(2,7,':');
//	
//	//显示“湿度:”
//	OLED_ShowChinese(3,2,2);
//	OLED_ShowChinese(3,3,3);
//	OLED_ShowChar(3,7,':');
//	
//	//显示”光照强度：“
//	OLED_ShowChinese(4, 2, 5);
//	OLED_ShowChinese(4, 3, 20);
//	OLED_ShowChinese(4, 4, 21);
//	OLED_ShowChinese(4, 5, 22);
//	OLED_ShowChar(4, 11, ':');

    // 第一行：显示"温度："（原第二行上移）
    OLED_ShowChinese(1, 2, 0);   // 温
    OLED_ShowChinese(1, 3, 1);   // 度
    OLED_ShowChar(1, 7, ':');
    
    // 第二行：显示"湿度："（原第三行上移）
    OLED_ShowChinese(2, 2, 2);   // 湿
    OLED_ShowChinese(2, 3, 3);   // 度
    OLED_ShowChar(2, 7, ':');
    
    // 第三行：显示"光照强度："（原第四行上移）
    OLED_ShowChinese(3, 2, 5);    // 光
    OLED_ShowChinese(3, 3, 20);   // 照
    OLED_ShowChinese(3, 4, 21);   // 强
    OLED_ShowChinese(3, 5, 22);   // 度
    OLED_ShowChar(3, 11, ':');
    
    // 第四行：新增"烟雾浓度："显示
    OLED_ShowChinese(4, 2, 32);    // 烟
    OLED_ShowChinese(4, 3, 33);      // 雾
    OLED_ShowChinese(4, 4, 34);     // 浓
    OLED_ShowChinese(4, 5, 35);   // 度
    OLED_ShowChar(4, 11, ':');

		
}

void OLED_Option(u8 num)
{
	switch(num)
	{
		case 1:
			OLED_ShowChar(1, 1, '>');
			OLED_ShowChar(2, 1, ' ');
			OLED_ShowChar(3, 1, ' ');
			OLED_ShowChar(4, 1, ' ');
			break;
		case 2:
			OLED_ShowChar(1, 1, ' ');
			OLED_ShowChar(2, 1, '>');
			OLED_ShowChar(3, 1, ' ');
			OLED_ShowChar(4, 1, ' ');
			break;
		case 3:
			OLED_ShowChar(1, 1, ' ');
			OLED_ShowChar(2, 1, ' ');
			OLED_ShowChar(3, 1, '>');
			OLED_ShowChar(4, 1, ' ');
			break;
        case 4:
			OLED_ShowChar(1, 1, ' ');
			OLED_ShowChar(2, 1, ' ');
			OLED_ShowChar(3, 1, ' ');
			OLED_ShowChar(4, 1, '>');
			break;
		default: break;
	}
}

void OLED_Option_open(u8 num)
{
    
	switch(num)
	{
		case 1:	
			OLED_ShowChar(1, 1, '>');
			OLED_ShowChar(2, 1, ' ');
			OLED_ShowChar(3, 1, ' ');
            OLED_ShowChar(4, 1, ' ');
			break;
		case 2:	
			OLED_ShowChar(1, 1, ' ');
			OLED_ShowChar(2, 1, '>');
			OLED_ShowChar(3, 1, ' ');
            OLED_ShowChar(4, 1, ' ');
			break;
		case 3:
			OLED_ShowChar(1, 1, ' ');
			OLED_ShowChar(2, 1, ' ');
			OLED_ShowChar(3, 1, '>');
            OLED_ShowChar(4, 1, ' ');
			break;
		case 4:
			OLED_ShowChar(1, 1, ' ');
			OLED_ShowChar(2, 1, ' ');
			OLED_ShowChar(3, 1, ' ');
            OLED_ShowChar(4, 1, '>');
			break;
		default: break;
	}
}

/* ASCII and Chinese menus use different columns; erase the previous layout once. */
static void OLED_BeginControlPage(uint8_t page)
{
    static uint8_t displayed_page = 0u;
    if (displayed_page != page) {
        OLED_Clear();
        displayed_page = page;
    }
}

void OLED_controlDevicePage1(void)
{
    OLED_BeginControlPage(1u);
                OLED_ShowChinese(1, 3, 28);  // 开
                OLED_ShowChinese(1, 4, 29);  // 打
                OLED_ShowChinese(1, 5, 4);   // 灯
                OLED_ShowChinese(1, 6, 5);   // 光
    
                OLED_ShowChinese(2, 3, 30);  // 关
                OLED_ShowChinese(2, 4, 31);  // 闭
                OLED_ShowChinese(2, 5, 4);   // 灯
                OLED_ShowChinese(2, 6, 5);   // 光
    
                OLED_ShowChinese(3, 3, 28);  // 开
                OLED_ShowChinese(3, 4, 29);  // 打
                OLED_ShowChinese(3, 5, 6);   // 风
                OLED_ShowChinese(3, 6, 7);   // 扇

                OLED_ShowChinese(4, 3, 30);  // 关
                OLED_ShowChinese(4, 4, 31);  // 闭
                OLED_ShowChinese(4, 5, 6);   // 风
                OLED_ShowChinese(4, 6, 7);   // 扇
}
void OLED_controlDevicePage2(void)
{
    OLED_BeginControlPage(2u);
                OLED_ShowChinese(1, 3, 28);  // 开
                OLED_ShowChinese(1, 4, 29);  // 打
                OLED_ShowChinese(1, 5, 8);   // 窗
                OLED_ShowChinese(1, 6, 9);   // 帘
    
                OLED_ShowChinese(2, 3, 30);  // 关
                OLED_ShowChinese(2, 4, 31);  // 闭
                OLED_ShowChinese(2, 5, 8);   // 窗
                OLED_ShowChinese(2, 6, 9);   // 帘
    
                OLED_ShowChinese(3, 3, 23);  // 手
                OLED_ShowChinese(3, 4, 24);  // 动
                OLED_ShowChinese(3, 5, 26);  // 模
                OLED_ShowChinese(3, 6, 27);  // 式

                OLED_ShowChinese(4, 3, 25);  // 自
                OLED_ShowChinese(4, 4, 24);  // 动
                OLED_ShowChinese(4, 5, 26);  // 模
                OLED_ShowChinese(4, 6, 27);  // 式


}

// 设备控制函数
/* Door commands share the existing device-control menu and four keys. */
void OLED_controlDoorPage(void)
{
    OLED_BeginControlPage(3u);
    /* Four Chinese cells per row, aligned with the other control pages. */
    OLED_ShowChinese(1, 3, 28);
    OLED_ShowChinese(1, 4, 29);
    OLED_ShowChinese(1, 5, 45);
    OLED_ShowChinese(1, 6, 46);
    OLED_ShowChinese(2, 3, 30);
    OLED_ShowChinese(2, 4, 31);
    OLED_ShowChinese(2, 5, 45);
    OLED_ShowChinese(2, 6, 46);
    OLED_ShowChinese(3, 3, 47);
    OLED_ShowChinese(3, 4, 48);
    if (MG90S_GetCommandedTarget() == MG90S_COMMAND_OPEN) {
        OLED_ShowChinese(3, 5, 18);
        OLED_ShowChinese(3, 6, 45);
    } else if (MG90S_GetCommandedTarget() == MG90S_COMMAND_CLOSE) {
        OLED_ShowChinese(3, 5, 19);
        OLED_ShowChinese(3, 6, 45);
    } else {
        OLED_ShowChinese(3, 5, 49);
        OLED_ShowChinese(3, 6, 50);
    }
    OLED_ShowString(4, 1, "                ");
}

void ControlDeviceSwitch(uint8_t selection, uint8_t page)
{
    /* Valid local commands supersede the displayed sleep/away scene. */
    if (((page == 1u || page == 2u) && selection >= 1u && selection <= 4u) ||
        (page == 3u && selection >= 1u && selection <= 2u)) {
        HomeScene_Apply(HOME_SCENE_NORMAL);
    }
    if(page == 1) {
        // 页面1：灯光和风扇控制
        switch(selection) {
            case 1: // 打开灯光
                USB_ON(1);
                break;
            case 2: // 关闭灯光
                USB_OFF(1);
                break;
            case 3: // 打开风扇
                USB_ON(2);
                break;
            case 4: // 关闭风扇
                USB_OFF(2);
                break;
        }
    } else if (page == 2) {
        // 页面2：窗帘和模式控制
        switch(selection) {
            case 1: // 打开窗帘
                Curtain_ON_Flag = 1;
                break;
            case 2: // 关闭窗帘
                Curtain_OFF_Flag = 1;
                break;
            case 3: // 手动模式
                modeee = 0; // 手动模式
                break;
            case 4: // 自动模式
                modeee = 1; // 自动模式
                break;
        }
    } else if (page == 3) {
        if (selection == 1) {
            MG90S_Open();
        } else if (selection == 2) {
            MG90S_Close();
        }
    }
}
