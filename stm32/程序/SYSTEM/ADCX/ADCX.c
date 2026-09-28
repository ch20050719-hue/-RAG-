#include "adcx.h"

//模拟量采集使用引脚：
//PA4,PA5,PA6,PA7
#define ADCX_POLL_LIMIT 100000u

static u8 adc_ready = 0u;

u8 Adc1_Channe_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
    ADC_InitTypeDef ADC_InitStructure;
    u32 timeout;

    adc_ready = 0u;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_ADC1,ENABLE);

    GPIO_InitStructure.GPIO_Mode=GPIO_Mode_AIN;
    GPIO_InitStructure.GPIO_Pin=GPIO_Pin_4|GPIO_Pin_5;
    GPIO_InitStructure.GPIO_Speed=GPIO_Speed_50MHz;
    GPIO_Init(GPIOA,&GPIO_InitStructure);

    ADC_DeInit(ADC1);
    ADC_InitStructure.ADC_ContinuousConvMode=DISABLE;
    ADC_InitStructure.ADC_DataAlign=ADC_DataAlign_Right;
    ADC_InitStructure.ADC_ExternalTrigConv=ADC_ExternalTrigConv_None;
    ADC_InitStructure.ADC_Mode=ADC_Mode_Independent;
    ADC_InitStructure.ADC_NbrOfChannel=1;
    ADC_InitStructure.ADC_ScanConvMode=DISABLE;
    ADC_Init(ADC1,&ADC_InitStructure);
    ADC_Cmd(ADC1,ENABLE);

    ADC_ResetCalibration(ADC1);
    timeout = ADCX_POLL_LIMIT;
    while (ADC_GetResetCalibrationStatus(ADC1) != RESET) {
        if (--timeout == 0u) return 0u;
    }

    ADC_StartCalibration(ADC1);
    timeout = ADCX_POLL_LIMIT;
    while (ADC_GetCalibrationStatus(ADC1) != RESET) {
        if (--timeout == 0u) return 0u;
    }
    adc_ready = 1u;
    return 1u;
}

u8 ADCX_ReadValue(u8 ch, u16 *value)
{
    u32 timeout = ADCX_POLL_LIMIT;
    if (!adc_ready) return 0u;
    ADC_RegularChannelConfig(ADC1,ch,1,ADC_SampleTime_239Cycles5);
    ADC_SoftwareStartConvCmd(ADC1,ENABLE);
    while (ADC_GetFlagStatus(ADC1,ADC_FLAG_EOC) == RESET) {
        if (--timeout == 0u) return 0u;
    }
    *value = ADC_GetConversionValue(ADC1);
    return 1u;
}
