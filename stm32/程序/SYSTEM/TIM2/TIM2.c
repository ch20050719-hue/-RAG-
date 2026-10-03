#include "stm32f10x.h"                  // Device header
#include "gizwits_product.h" 
#include "tim2.h"                  // Device header
#include "usb.h"
#include "motor.h"
#include "usart.h"
#include "MG90S.h"	

uint8_t modeee=0;
extern    u8 Curtain_OFF_Flag;
extern    u8 Curtain_ON_Flag;
// ����ȫ�ֱ�������¼��һ�ε�ģʽ״̬
static uint8_t last_mode = 0;
static uint8_t first_switch_to_manual = 0;
static volatile uint8_t current_home_scene = HOME_SCENE_NORMAL;
static volatile uint8_t provision_request = 0u;

uint8_t Provision_TakeRequest(void)
{
    uint8_t requested;
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    requested = provision_request;
    provision_request = 0u;
    __set_PRIMASK(primask);
    return requested;
}

void HomeScene_Apply(uint8_t scene)
{
    if (scene == HOME_SCENE_NORMAL)
    {
        current_home_scene = HOME_SCENE_NORMAL;
    }
    else if (scene == HOME_SCENE_SLEEP)
    {
        /* Sleep: fan on, light off, door close/lock target. */
        modeee = 0u;
        last_mode = 0u;
        first_switch_to_manual = 0u;
        USB_ON(2);
        USB_OFF(1);
        MG90S_Close();
        current_home_scene = HOME_SCENE_SLEEP;
    }
    else if (scene == HOME_SCENE_AWAY)
    {
        /* Away: light off, fan off, door close target. */
        modeee = 0u;
        last_mode = 0u;
        first_switch_to_manual = 0u;
        USB_OFF(1);
        USB_OFF(2);
        MG90S_Close();
        current_home_scene = HOME_SCENE_AWAY;
    }
}

uint8_t HomeScene_GetCurrent(void)
{
    return current_home_scene;
}


void AppTimer1_Init(u16 Prescaler, u16 Period)	//0-65535
{
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_TIM1, ENABLE);
	
	TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStructure;
	TIM_TimeBaseInitStructure.TIM_ClockDivision = TIM_CKD_DIV1;
	TIM_TimeBaseInitStructure.TIM_CounterMode = TIM_CounterMode_Up;
	TIM_TimeBaseInitStructure.TIM_Period = Period;
	TIM_TimeBaseInitStructure.TIM_Prescaler = Prescaler;
	TIM_TimeBaseInitStructure.TIM_RepetitionCounter = 0;
	
	TIM_TimeBaseInit(TIM1, &TIM_TimeBaseInitStructure);
	
	TIM_ITConfig(TIM1, TIM_IT_Update, ENABLE);
	
	
	NVIC_InitTypeDef NVIC_InitStructure;
	NVIC_InitStructure.NVIC_IRQChannel = TIM1_UP_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 2;
	NVIC_Init(&NVIC_InitStructure);
	
	TIM_Cmd(TIM1, ENABLE);
}
// ȫ�ֱ�������
volatile uint32_t timer2_counter = 0;  // 2ms�жϼ�����
volatile uint32_t seconds_count = 0;   // �������
void TIM1_UP_IRQHandler(void)	//2ms��ʱ�ж�
{
	if (TIM_GetITStatus(TIM1, TIM_IT_Update) != RESET ) 
	{
		Key_scan();
		if (KeyNum == 44u && Menu == 1u)
		{
			KeyNum = 0u;
			provision_request = 1u;
		}

		if(KeyNum == 1 && Menu == 1)
		{
			KeyNum = 0;
			Menu = 2;
		}
//        timer2_counter++;  // 2ms��������1
//        if(timer2_counter >= 500)
//        {
//            timer2_counter = 0;      // ����2ms������
//            seconds_count++;         // ���������1
//            
//        OLED_ShowNum(4,1,seconds_count,3);
//        }
		
//		if(mode)//�Զ�ģʽmode-==1
//		{
//			// ͳһ����USB�ͷ�����
//                uint8_t need_alert = 0;

//                if(Temp_value < Temp)
//                {
//                need_alert = 1;
//                }

//                if(Humi_value < Humi)
//                {
//                need_alert = 1;

//                if(!CurtainFlag)
//                {
//                    Curtain_ON_Flag = 1;
//                }
//                }
//                else
//                {
//                if(CurtainFlag)
//                {
//                    Curtain_OFF_Flag = 1;
//                }
//                }

//                // ͳһ����USB�ͷ�����
//                if(need_alert)
//                {
//                Buzzer_ON();
//                USB_ON(2);
//                }
//                else
//                {
//                Buzzer_OFF();
//                USB_OFF(2);
//                }
//                
//                
//             if(Lux < Lux_value)
//			{
//				USB_ON(1);
//			}
//			else
//			{
//				USB_OFF(1);
//			}
//		}
//        if(modeee) // �Զ�ģʽ mode == 1
//    {
//        
//        // 2. ��ʼ�����豸���Ʊ�־
//        uint8_t temp_alert = 0;
//        uint8_t humi_alert = 0;
//        uint8_t smoke_alert = 0;
//        
//        // 3. �¶ȼ�������
//        if(Temp_value < Temp)
//        {
//            temp_alert = 1;
//        }
//        
//        // 4. ʪ�ȼ�������
//        if(Humi_value < Humi)
//        {
//            humi_alert = 1;
//            if(!CurtainFlag)  // �����ر�ʱ��
//            {
//                Curtain_ON_Flag = 1;
//            }
//        }
//        else
//        {
//            if(CurtainFlag)  // ������ʱ�ر�
//            {
//                Curtain_OFF_Flag = 1;
//            }
//        }
//        
//        // 5. ����Ũ�ȼ������ƣ�������
//        if(Smoke > Smoke_value)  // ����Ũ�ȸ�����ֵ
//        {
//            smoke_alert = 1;
//            
//            // ��������ͨ�磨�������Ĵ��������߼���
//            if(!CurtainFlag)  // ��������رգ����
//            {
//                Curtain_ON_Flag = 1;  // ��Ҫ���崰���򿪱�־
//            }
//            
//            // ��������ͨ��
//            USB_ON(2);  // ����
//            
//            // ����������
//            Buzzer_ON();
//        }
//        else
//        {
//            // ����Ũ���������رշ��ȣ����������������Ŀ��ƣ�
//            if(!temp_alert && !humi_alert)  // ֻ���¶Ⱥ�ʪ�ȶ�����Ҫ����ʱ�Źر�
//            {
//                USB_OFF(2);  // �رշ���
//            }
//            
//            // �رշ���������������������������
//            if(!temp_alert && !humi_alert)
//            {
//                Buzzer_OFF();
//            }
//            
//            // �������Ӵ����ر��߼���������������������
//            // if(WindowFlag && ��������) { Window_Close_Flag = 1; }
//        }
//        
//        // 6. ͳһ�����߼������ȼ������� > �¶� > ʪ�ȣ�
//        if(smoke_alert)
//        {
//            // �����������ȼ����
//            Buzzer_ON();
//            USB_ON(2);  // ����
//            // �����Ѿ���������ⲿ�ֿ���
//        }
//        else if(temp_alert || humi_alert)
//        {
//            // �¶Ȼ�ʪ�ȱ���
//            Buzzer_ON();
//            USB_ON(2);  // ����
//        }
//        else
//        {
//            // ���в�������
//            Buzzer_OFF();
//            USB_OFF(2);  // �رշ���
//        }
//        
//        // 7. �ƹ���ƣ������ڱ���ϵͳ��
//        if(Lux < Lux_value)
//        {
//            USB_ON(1);  // �򿪵ƹ�
//        }
//        else
//        {
//            USB_OFF(1); // �رյƹ�
//        }
//    }

		TIM_ClearITPendingBit(TIM1, TIM_IT_Update);
	}
}

void HomeControl_Process(uint8_t pause_auto)
{
uint8_t command = 0u;
uint8_t has_command = USART1_TakeCommand(&command);
    if (has_command)
    {
    if (command >= 0x01u && command <= MG90S_CMD_CLOSE)
    {
        HomeScene_Apply(HOME_SCENE_NORMAL);
    }
    switch(command)
    {
        case 0x01:  // �򿪵ƹ�
            // ִ�п��Ʋ���������GPIO��̵�����
                USB_ON(1);
            break;
            
        case 0x02:  // �رյƹ�
                USB_OFF(1);
            break;
            
        case 0x03:  // ������
                USB_ON(2);
            break;
            
        case 0x04:  // �ط���
                USB_OFF(2);
            break;
            
        case 0x05:  // ������
                Curtain_ON_Flag = 1;
            break;
            
        case 0x06:  // �ش���
                Curtain_OFF_Flag = 1;
            break;
            
        case 0x07:  // �ֶ�ģʽ
                modeee = 0; // �ֶ�ģʽ
            break;
            
        case 0x08:  // �Զ�ģʽ
                modeee = 1; // �Զ�ģʽ
            break;
            
        case MG90S_CMD_OPEN:
            MG90S_Open();
            break;

        case MG90S_CMD_CLOSE:
            MG90S_Close();
            break;

        case HOME_SCENE_CMD_SLEEP:
            HomeScene_Apply(HOME_SCENE_SLEEP);
            break;

        case HOME_SCENE_CMD_AWAY:
            HomeScene_Apply(HOME_SCENE_AWAY);
            break;

        default:    // δ֪����
            break;
    }
}
if (pause_auto) return;
if(modeee) // �Զ�ģʽ mode == 1
{
    // ��¼��ǰΪ�Զ�ģʽ
    last_mode = 1;
    first_switch_to_manual = 1; // ���ñ�־��Ϊ�´��л���׼��
    // 2. ��ʼ�����豸���Ʊ�־
    uint8_t temp_alert = 0;
    uint8_t humi_alert = 0;
    uint8_t smoke_alert = 0;
    
    // 3. �¶ȼ�������
    if(DHT11_DataValid && Temp_value < Temp)
    {
        temp_alert = 1;
    }
    
    // 4. ʪ�ȼ�������
    if(DHT11_DataValid && Humi_value < Humi)
    {
        humi_alert = 1;
        if(!CurtainFlag)  // �����ر�ʱ��
        {
            Curtain_ON_Flag = 1;
        }
    }
    else if (DHT11_DataValid)
    {
        if(CurtainFlag)  // ������ʱ�ر�
        {
            Curtain_OFF_Flag = 1;
        }
    }
    
    // 5. ����Ũ�ȼ������ƣ��޸ģ��Ƴ��������ƣ�
    if(ADC_DataValid && Smoke > Smoke_value)  // ����Ũ�ȸ�����ֵ
    {
        smoke_alert = 1;
        
        // �Ƴ��������߼�
        // ֻ�������Ⱥͷ�����
        
        // ��������ͨ��
        USB_ON(2);  // ����
        
        // ����������
        Buzzer_ON();
    }
    else if (ADC_DataValid && DHT11_DataValid)
    {
        // ����Ũ���������رշ��ȣ����������������Ŀ��ƣ�
        if(!temp_alert && !humi_alert)  // ֻ���¶Ⱥ�ʪ�ȶ�����Ҫ����ʱ�Źر�
        {
            USB_OFF(2);  // �رշ���
        }
        
        // �رշ���������������������������
        if(!temp_alert && !humi_alert)
        {
            Buzzer_OFF();
        }
    }
    
    // 6. ͳһ�����߼������ȼ������� > �¶� > ʪ�ȣ�
    if(smoke_alert)
    {
        // �����������ȼ����
        Buzzer_ON();
        USB_ON(2);  // ����
        // �Ƴ������������ע��
    }
    else if(temp_alert || humi_alert)
    {
        // �¶Ȼ�ʪ�ȱ���
        Buzzer_ON();
        USB_ON(2);  // ����
    }
    else if (DHT11_DataValid && ADC_DataValid)
    {
        // ���в�������
        Buzzer_OFF();
        USB_OFF(2);  // �رշ���
    }
    
    // 7. �ƹ���ƣ������ڱ���ϵͳ��
    if(ADC_DataValid && Lux < Lux_value)
    {
        USB_ON(1);  // �򿪵ƹ�
    }
    else if (ADC_DataValid)
    {
        USB_OFF(1); // �رյƹ�
    }
}
else // �ֶ�ģʽ
{
    // ����Ƿ�մ��Զ�ģʽ�л��������״��л���
    if(last_mode == 1 && first_switch_to_manual) 
    {
        // ִֻ��һ�Σ��ر�����������
        Buzzer_OFF();      // �رշ�����
        USB_OFF(1);        // �رյƹ�
        USB_OFF(2);        // �رշ���
        Curtain_OFF_Flag = 1;
        // ���ñ�־��ȷ��ִֻ��һ��
        first_switch_to_manual = 0;
        
        // ��������������Ҫ�رյ��豸
        // USB_OFF(3);  // ����������豸
    }
    
    // ��¼��ǰΪ�ֶ�ģʽ
    last_mode = 0;
    
    // �ֶ�ģʽ�µ����������߼�
    // �����û�ͨ�����水ť�����豸��
}
}

