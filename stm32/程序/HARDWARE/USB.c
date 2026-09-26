#include "usb.h"

u8 FanFlag,LEDFlag;

void USB_Init(void)
{
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);
	
	GPIO_InitTypeDef GPIO_InitStructure;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Pin = USB1 | USB2;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOB, &GPIO_InitStructure);
	
}

void USB_ON(u8 num)
{
	if(num == 1)
	{
		GPIO_SetBits(GPIOB, USB1);	
		LEDFlag = 1;	
	}
	else
	{
		GPIO_SetBits(GPIOB, USB2);
		FanFlag = 1;		
	}
}

void USB_OFF(u8 num)
{
	
	if(num == 1)
	{
		GPIO_ResetBits(GPIOB, USB1);
		LEDFlag = 0;		
	}
	else
	{
		GPIO_ResetBits(GPIOB, USB2);
		FanFlag = 0;		
	}	
}


