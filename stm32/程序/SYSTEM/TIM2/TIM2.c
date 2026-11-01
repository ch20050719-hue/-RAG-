#include "stm32f10x.h"                  // Device header
#include "gizwits_product.h" 
#include "tim2.h"                  // Device header
#include "usb.h"
#include "motor.h"
#include "usart.h"
#include "auto_control_logic.h"
#include "MG90S.h"	

uint8_t modeee=0;
extern    u8 Curtain_OFF_Flag;
extern    u8 Curtain_ON_Flag;
// ����ȫ�ֱ�������¼��һ�ε�ģʽ״̬
static uint8_t last_mode = 0;
static volatile uint8_t current_home_scene = HOME_SCENE_NORMAL;
static AutoControlState auto_control_state = {0u, 0u, 0u, 0u};

void HomeScene_Apply(uint8_t scene)
{
    if (scene == HOME_SCENE_NORMAL)
    {
        current_home_scene = HOME_SCENE_NORMAL;
    }
    else if (scene == HOME_SCENE_SLEEP || scene == HOME_SCENE_AWAY)
    {
        /* Both presets use manual control, light off and a closed door target. */
        modeee = 0u;
        last_mode = 0u;
        USB_OFF(1);
        MG90S_Close();
        if (scene == HOME_SCENE_SLEEP)
        {
            USB_ON(2);
            Curtain_ON_Flag = 0u;
            Curtain_OFF_Flag = 1u;
        }
        else
        {
            USB_OFF(2);
        }
        current_home_scene = scene;
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

/* Apply mode cleanup before device commands, even during provisioning feedback. */
void HomeControl_SyncMode(void)
{
    if (!modeee)
    {
        const AutoControlState clear_state = {0u, 0u, 0u, 0u};
        auto_control_state = clear_state;
        if (last_mode)
        {
            Buzzer_OFF();
            USB_OFF(1);
            USB_OFF(2);
            Curtain_ON_Flag = 0u;
            Curtain_OFF_Flag = 1u;
        }
    }
    last_mode = modeee ? 1u : 0u;
}
void HomeControl_Process(uint8_t pause_auto)
{
uint8_t command = 0u;
uint8_t has_command;
HomeControl_SyncMode();
has_command = USART1_TakeCommand(&command);
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
                Curtain_OFF_Flag = 0u;
                Curtain_ON_Flag = 1;
            break;
            
        case 0x06:  // �ش���
                Curtain_ON_Flag = 0u;
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

        case HOME_SCENE_CMD_WAKEUP:
            /* Keep the window target and prevent later mode cleanup. */
            modeee = 0u;
            last_mode = 0u;
            Buzzer_OFF();
            USB_ON(1);
            USB_OFF(2);
            MG90S_Open();
            current_home_scene = HOME_SCENE_NORMAL;
            break;

        case HOME_SCENE_CMD_AWAY:
            HomeScene_Apply(HOME_SCENE_AWAY);
            break;

        default:    // δ֪����
            break;
    }
}
HomeControl_SyncMode();
if (pause_auto) return;
if(modeee) // �Զ�ģʽ mode == 1
{
    // 2. ��ʼ�����豸���Ʊ�־
    uint8_t temp_alert;
    uint8_t humi_alert;
    uint8_t smoke_alert;
    AutoControlInputs input;
    input.temperature = Temp;
    input.humidity = Humi;
    input.light = Lux;
    input.smoke = Smoke;
    input.temperature_threshold = Temp_value;
    input.humidity_threshold = Humi_value;
    input.light_threshold = Lux_value;
    input.smoke_threshold = Smoke_value;
    input.dht_valid = DHT11_DataValid;
    input.adc_valid = ADC_DataValid;
    auto_control_state = AutoControl_Evaluate(auto_control_state, input);
    temp_alert = DHT11_DataValid && auto_control_state.temperature;
    humi_alert = DHT11_DataValid && auto_control_state.humidity;
    smoke_alert = ADC_DataValid && auto_control_state.smoke;
    
    // 3. �¶ȼ�������
    if(temp_alert)
    {
        temp_alert = 1;
    }
    
    // 4. ʪ�ȼ�������
    if(humi_alert)
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
    if(smoke_alert)  // ����Ũ�ȸ�����ֵ
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
    if(ADC_DataValid && auto_control_state.light)
    {
        USB_ON(1);  // �򿪵ƹ�
    }
    else if (ADC_DataValid)
    {
        USB_OFF(1); // �رյƹ�
    }
}
}
