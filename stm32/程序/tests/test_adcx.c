#include <assert.h>
#include "../SYSTEM/ADCX/ADCX.h"

static int reset_busy, calibrate_busy, eoc_busy;
static int reset_calls, calibrate_calls, eoc_calls, conversion_calls;
static u8 last_channel;

void RCC_APB2PeriphClockCmd(uint32_t p, int e) { (void)p; (void)e; }
void GPIO_Init(GPIO_TypeDef *p, GPIO_InitTypeDef *c) { (void)p; (void)c; }
void ADC_DeInit(ADC_TypeDef *a) { (void)a; }
void ADC_Init(ADC_TypeDef *a, ADC_InitTypeDef *c) { (void)a; (void)c; }
void ADC_Cmd(ADC_TypeDef *a, int e) { (void)a; (void)e; }
void ADC_ResetCalibration(ADC_TypeDef *a) { (void)a; }
FlagStatus ADC_GetResetCalibrationStatus(ADC_TypeDef *a)
{ (void)a; ++reset_calls; return reset_busy; }
void ADC_StartCalibration(ADC_TypeDef *a) { (void)a; }
FlagStatus ADC_GetCalibrationStatus(ADC_TypeDef *a)
{ (void)a; ++calibrate_calls; return calibrate_busy == 2 || (calibrate_busy == 1 && calibrate_calls < 3); }
void ADC_RegularChannelConfig(ADC_TypeDef *a, u8 ch, int rank, int sample)
{ (void)a; (void)rank; (void)sample; last_channel = ch; }
void ADC_SoftwareStartConvCmd(ADC_TypeDef *a, int e) { (void)a; (void)e; }
FlagStatus ADC_GetFlagStatus(ADC_TypeDef *a, u8 flag)
{ (void)a; (void)flag; ++eoc_calls; return eoc_busy ? RESET : SET; }
u16 ADC_GetConversionValue(ADC_TypeDef *a)
{ (void)a; ++conversion_calls; return 1234; }

int main(void)
{
    u16 value = 99;
    reset_busy = 1;
    assert(Adc1_Channe_Init() == 0);
    assert(ADCX_ReadValue(5, &value) == 0);
    assert(value == 99);

    reset_busy = 0; calibrate_busy = 2; calibrate_calls = 0;
    assert(Adc1_Channe_Init() == 0);
    assert(ADCX_ReadValue(5, &value) == 0);

    calibrate_busy = 1; calibrate_calls = 0;
    assert(Adc1_Channe_Init() == 1);
    assert(calibrate_calls == 3);
    eoc_busy = 0;
    assert(ADCX_ReadValue(5, &value) == 1);
    assert(value == 1234 && last_channel == 5);

    eoc_busy = 1; value = 99; conversion_calls = 0;
    assert(ADCX_ReadValue(4, &value) == 0);
    assert(value == 99 && conversion_calls == 0);
    return 0;
}
