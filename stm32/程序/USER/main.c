#include "stm32f10x.h"
#include "led.h"
#include "usart.h"
#include "delay.h"
#include "dht11.h"
#include "oled.h"
#include "motor.h"
#include "buzzer.h"
#include "usb.h"
#include "tim2.h"
#include "menu.h"
#include "key.h"
#include "tim3.h"
#include "ldr.h"
#include "iwdg.h"
#include "gizwits_product.h"
#include "adcx.h"
#include "MG90S.h"
#include "threshold_step.h"


u8 temp;
u8 humi;
u8 Menu = 1;	//�˵�����

u8 SetNum = 1;	

u8 Temp_value=40;	//�¶���ֵ����
u8 Humi_value=80;	//ʪ����ֵ����
u16 Lux_value=80;  //����ǿ��
u16 Smoke_value=2000;    //����Ũ��


u8 Curtain_OFF_Flag;
u8 Curtain_ON_Flag;
// ȫ�ֱ���
uint8_t deviceSelection = 1;    // ��ǰѡ����豸�� (1-4)
uint8_t devicePage = 1;    // Device control menu page 1..3

uint8_t current_screen = 0; // 0:��ʾ�˵�1, 1:��ʾ�˵�11
int main(void)
{
    uint32_t last_tim3_heartbeat = 0u;
    uint32_t last_sensor_sample_ms = 0u;
    uint32_t provision_started_ms = 0u;
    uint8_t sensor_sampled = 0u;
    uint8_t provision_feedback_active = 0u;
	
    SystemInit();//����ϵͳʱ��Ϊ72M	
	
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
	delay_init(72);
	uart1_init(9600);
	LED_Init();
    MOTOR_UserConfig();//�����ʼ���ɹ�
    DHT11_UserConfig();//dht11��ʼ���ɹ�
    	Key_Init();
	USB_Init();
	Buzzer_Init();
    
    MG90S_Init();
	uart2_init(9600);
    
	OLED_Init();//OLED��ʾ����ʼ���ɹ�
    
    if (Adc1_Channe_Init() == 0u)
    {
        printf("ADC calibration failed\r\n");
    }
	LED_On();
	userInit();	//��ɳ�ʼ��ֵ
	gizwitsInit();
    IWDG_Init();
    GENERAL_TIM_Init();
    AppTimer1_Init(9,14398);
  while (1)
  {
		uint32_t now_ms = g_tim3_heartbeat;
		if (!sensor_sampled || (uint32_t)(now_ms - last_sensor_sample_ms) >= 1000u)
		{
			last_sensor_sample_ms = now_ms;
			sensor_sampled = 1u;
			Menu_UpdateSensors(now_ms);
		}
		if (Provision_TakeRequest())
		{
			if (gizwitsSetMode(2u) >= 0)
			{
				Buzzer_ON();
				provision_started_ms = g_tim3_heartbeat;
				provision_feedback_active = 1u;
			}
			else
			{
				printf("WiFi config send failed\r\n");
			}
		}
		if (provision_feedback_active &&
			(uint32_t)(g_tim3_heartbeat - provision_started_ms) >= 300u)
		{
			Buzzer_OFF();
			provision_feedback_active = 0u;
		}
		HomeControl_Process(provision_feedback_active);
      		if (g_tim3_heartbeat != last_tim3_heartbeat)
        {
            last_tim3_heartbeat = g_tim3_heartbeat;
            IWDG_ReloadCounter();
        } //���¼��ؼ���ֵ ι��

		switch(Menu)
			{
				case 1:
                    
                 // ���ݵ�ǰ״̬������ʾ��Ӧ����Ļ
                    if(current_screen == 0)
                    {
                        Menu1();    // ������ʾ�˵�1
                    }
                    else
                    {
                        Menu11();   // ������ʾ�˵�11
                    }
                    // ��ⰴ���л�
                    if(KeyNum == 2)
                    {
                        KeyNum = 0;
                        OLED_Clear();
                        current_screen = !current_screen; // �л���Ļ״̬
                    }                    
                    
					if(KeyNum == 3)    //�ж��û��Ƿ����˳�����
					{
						KeyNum = 0;
						OLED_Clear();   //����
						Menu = 4;
					}
				break;
					
				case 2:
					OLED_Clear();	//����
					Menu2();	//��ʾ�˵�2
					Menu = 3;	
                    break;
				case 3:
					OLED_Option(SetNum);	//��ʾ��ǰѡ���λ��
					OLED_ShowNum(1,9,Temp_value,3);	//��ʾ�¶���ֵ����
					OLED_ShowNum(2,9,Humi_value,3);	//��ʾʪ����ֵ����
					OLED_ShowNum(3,13,Lux_value, 4);
					OLED_ShowNum(4,13,Smoke_value, 4);
				
					/*�ۼư���1���µĴ���*/
					if(KeyNum == 1)
					{
						KeyNum = 0;
						SetNum++;
						if(SetNum > 4)
						{
							SetNum = 1;
						}
					}
					
					/*��λ��ָ���¶���ֵ���ݰ���3��4������ֵ*/
					if(SetNum == 1)
					{
						if(KeyNum == 3)
						{
							KeyNum = 0;
							Temp_value = Threshold_Up8(Temp_value);
						}
						if(KeyNum == 4)
						{
							KeyNum = 0;
							Temp_value = Threshold_Down8(Temp_value);
						}
					}

					/*��λ��ָ��ʪ����ֵ���ݰ���3��4������ֵ*/
					if(SetNum == 2)
					{
						if(KeyNum == 3)
						{
							KeyNum = 0;
							Humi_value = Threshold_Up8(Humi_value);
						}
						if(KeyNum == 4)
						{
							KeyNum = 0;
							Humi_value = Threshold_Down8(Humi_value);
						}
					}
										
					if(SetNum == 3)
					{
						if(KeyNum == 3)
						{
							KeyNum = 0;
							Lux_value = Threshold_Up16(Lux_value);
						}
						if(KeyNum == 4)
						{
							KeyNum = 0;
							Lux_value = Threshold_Down16(Lux_value);
						}
					}
                    if(SetNum == 4)
					{
						if(KeyNum == 3)
						{
							KeyNum = 0;
							Smoke_value = Threshold_Up16(Smoke_value);
						}
						if(KeyNum == 4)
						{
							KeyNum = 0;
							Smoke_value = Threshold_Down16(Smoke_value);
						}
					}
					/*������2����ʱ�ص����˵�*/
					if(KeyNum == 2)
					{
						KeyNum = 0;
						
						OLED_Clear();	//����
						Menu = 1;	//��ʾ�˵�1
					}
					break;
				case 4:
//					ControlDeviceSwitch(ControlDeviceSetSelection());  //���ڴ�������ֵ
//					ControlDeviceOLED_Option(ControlDeviceSetSelection());    //��ȡ�����������Ӷ��жϡ�>����ʾλ��
//					//��������С�ڵ���4ʱ����ʾ����ҳ��1
//					if (ControlDeviceSetSelection() <= 4)
//					{
//						OLED_controlDevicePage1();   //��ʾ��ֵ���ý���1�̶���Ϣ
//	
//					}
//					else
//					{
//						OLED_controlDevicePage2();   //��ʾ��ֵ���ý���1�̶���Ϣ
//	
//					}	
//  

                
            // ������������
                switch(KeyNum) {
                    case 1: // �ϼ� - ����ѡ��// �¼� - ����ѡ��/��ת��һҳ
                        if(deviceSelection < (devicePage == 3 ? 2 : 4)) {
                            deviceSelection++;  // ����ѡ��
                        } else {
                            // ��������һ����¼�����ת��һҳ
                            if(devicePage < 3) {
                                devicePage++;
                            } else {
                                devicePage = 1; // �л���ҳ��1
                            }
                            deviceSelection = 1; // ����ѡ�񵽵�һ��
                        }
                        break;
                        
                    case 2: 
                        ControlDeviceSwitch(deviceSelection, devicePage);
                        break;
                }
                
                        // ������ʾ
                        if(devicePage == 1) {
                            OLED_controlDevicePage1();   // ��ʾ�豸����ҳ��1
                        } else if (devicePage == 2) {
                            OLED_controlDevicePage2();
                        } else {
                            OLED_controlDoorPage();
                        }
                        
                        // ��ʾѡ���ͷ
            OLED_Option_open(deviceSelection);
            
    
					if (KeyNum == 3 || KeyNum == 4)    //�ж��û��Ƿ����˳�����
					{
						KeyNum = 0;
						OLED_Clear();   //����
						Menu = 1;   //�ص���ҳ��1
					}	
    KeyNum = 0;
                    
					break;	
				default : break;
		}
		
		/*�жϵ��������־λ�Ƿ�Ϊ1*/
		if(Curtain_ON_Flag == 1 && CurtainFlag == 0)
		{
			CurtainFlag = 1;
			MOTOR_Direction_Angle(1, 0, 180, 1);   //˳ʱ������ת 180��
			MOTOR_STOP();   //���ֹͣ
		}
		Curtain_ON_Flag = 0;

		/*�жϵ���رձ�־λ�Ƿ�Ϊ1*/
		if(Curtain_OFF_Flag == 1 && CurtainFlag == 1)
		{
			CurtainFlag = 0;
			MOTOR_Direction_Angle(0, 0, 180, 1);   //��ʱ������ת 180��
			MOTOR_STOP();   //���ֹͣ
		}
		Curtain_OFF_Flag = 0; 

		userHandle();
		gizwitsHandle((dataPoint_t *)&currentDataPoint);
        Delay_ms(120);
	}
}




