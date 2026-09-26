#include "adcx.h"

//模拟量采集使用引脚：
//PA4,PA5,PA6,PA7
void Adc1_Channe_Init(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;
	ADC_InitTypeDef ADC_InitStructure;
	
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_ADC1,ENABLE);
	
	GPIO_InitStructure.GPIO_Mode=GPIO_Mode_AIN;
	GPIO_InitStructure.GPIO_Pin=GPIO_Pin_4|GPIO_Pin_5;
	GPIO_InitStructure.GPIO_Speed=GPIO_Speed_50MHz;
	GPIO_Init(GPIOA,&GPIO_InitStructure);
	
	ADC_DeInit(ADC1);
	
	ADC_InitStructure.ADC_ContinuousConvMode=DISABLE;//连续转化模式设置
	ADC_InitStructure.ADC_DataAlign=ADC_DataAlign_Right;//数据左对齐
	ADC_InitStructure.ADC_ExternalTrigConv=ADC_ExternalTrigConv_None;//软件触发
	ADC_InitStructure.ADC_Mode=ADC_Mode_Independent;//独立模式
	ADC_InitStructure.ADC_NbrOfChannel=1;//通道数
	ADC_InitStructure.ADC_ScanConvMode=DISABLE;//扫描模式设置
	ADC_Init(ADC1,&ADC_InitStructure);
	
	//ADC_TempSensorVrefintCmd(ENABLE); //开启内部温度传感器
	
	ADC_Cmd(ADC1,ENABLE);//使能指定ADC外设
	
	ADC_ResetCalibration(ADC1);//使能复位校准
	while(ADC_GetResetCalibrationStatus(ADC1));//等待复位校准结束
	ADC_StartCalibration(ADC1);//开启AD校准
	ADC_GetCalibrationStatus(ADC1);//等待AD校准结束
}

u16 get_Adc_Value(u8 ch)//通道一采样值
{	
   ADC_RegularChannelConfig(ADC1,ch,1,ADC_SampleTime_239Cycles5);
	 ADC_SoftwareStartConvCmd(ADC1,ENABLE);
	 while(!ADC_GetFlagStatus(ADC1,ADC_FLAG_EOC));
	 return ADC_GetConversionValue(ADC1);
}



