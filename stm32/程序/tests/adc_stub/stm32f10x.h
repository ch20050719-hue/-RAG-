#ifndef ADC_TEST_STM32_H
#define ADC_TEST_STM32_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef struct { int unused; } ADC_TypeDef;
typedef struct { int unused; } GPIO_TypeDef;
typedef struct { uint32_t GPIO_Mode, GPIO_Pin, GPIO_Speed; } GPIO_InitTypeDef;
typedef struct {
    uint32_t ADC_ContinuousConvMode, ADC_DataAlign, ADC_ExternalTrigConv;
    uint32_t ADC_Mode, ADC_NbrOfChannel, ADC_ScanConvMode;
} ADC_InitTypeDef;
typedef int FlagStatus;
#define ENABLE 1
#define DISABLE 0
#define RESET 0
#define SET 1
#define RCC_APB2Periph_GPIOA 1u
#define RCC_APB2Periph_ADC1 2u
#define GPIO_Mode_AIN 1u
#define GPIO_Pin_4 16u
#define GPIO_Pin_5 32u
#define GPIO_Speed_50MHz 1u
#define ADC_DataAlign_Right 1u
#define ADC_ExternalTrigConv_None 1u
#define ADC_Mode_Independent 1u
#define ADC_SampleTime_239Cycles5 1u
#define ADC_FLAG_EOC 2u
#define ADC1 ((ADC_TypeDef *)1)
#define GPIOA ((GPIO_TypeDef *)2)
void RCC_APB2PeriphClockCmd(uint32_t p, int e);
void GPIO_Init(GPIO_TypeDef *p, GPIO_InitTypeDef *c);
void ADC_DeInit(ADC_TypeDef *a);
void ADC_Init(ADC_TypeDef *a, ADC_InitTypeDef *c);
void ADC_Cmd(ADC_TypeDef *a, int e);
void ADC_ResetCalibration(ADC_TypeDef *a);
FlagStatus ADC_GetResetCalibrationStatus(ADC_TypeDef *a);
void ADC_StartCalibration(ADC_TypeDef *a);
FlagStatus ADC_GetCalibrationStatus(ADC_TypeDef *a);
void ADC_RegularChannelConfig(ADC_TypeDef *a, u8 ch, int rank, int sample);
void ADC_SoftwareStartConvCmd(ADC_TypeDef *a, int e);
FlagStatus ADC_GetFlagStatus(ADC_TypeDef *a, u8 flag);
u16 ADC_GetConversionValue(ADC_TypeDef *a);
#endif
