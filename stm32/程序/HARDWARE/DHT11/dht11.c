#include "dht11.h"

/* DHT11 pulses are shorter than 100 us. A missing edge ends this reading. */
static u8 DHT11_WaitWhile(u8 level)
{
	u8 elapsed = 0;
	while(GPIO_ReadInputDataBit(DHT11_PROT, DHT11) == level)
	{
		if (++elapsed >= 100u) return 0u;
		Delay_us(1);
	}
	return 1u;
}

void DHT11_UserConfig(void)
{
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_AFIO,ENABLE);
	GPIO_PinRemapConfig(GPIO_Remap_SWJ_JTAGDisable,ENABLE);
}

void DHT11_Mode(u8 mode)
{
	GPIO_InitTypeDef GPIO_InitStructure;
	
	if(mode)
	{
		GPIO_InitStructure.GPIO_Pin = DHT11;
		GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
		GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
	}
	else
	{
		GPIO_InitStructure.GPIO_Pin =  DHT11;
		GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	}
	GPIO_Init(DHT11_PROT,&GPIO_InitStructure);
}

void DHT11_Sends_Start(void)
{
	DHT11_Mode(OUT);
	
	DHT11_Low;
	Delay_ms(18);	//18ms
	DHT11_High;
	Delay_us(40);	//40us
}

static u8 DHT11_Sends_Response(void)
{
	DHT11_Mode(INT);
	if (!DHT11_WaitWhile(0u)) return 0u; // 80 us low response
	return DHT11_WaitWhile(1u);           // 80 us high response
}

static u8 DHT11_Read_Byte(u8 *value)
{
	u8 data = 0;
	u8 i;
	for(i = 0; i < 8u; i++)
	{
		if (!DHT11_WaitWhile(0u)) return 0u;
		data <<= 1;
		Delay_us(40); // The high pulse is about 26 us for 0, 70 us for 1.
		if(GPIO_ReadInputDataBit(DHT11_PROT, DHT11) == 1)
		{
			data |= 0x01;
		}
		if (!DHT11_WaitWhile(1u)) return 0u;
	}
	*value = data;
	return 1u;
}

u8 DHT11_Read_Data(u8 *humi, u8 *temp)
{
	u8 DATA[5] = {0,0,0,0,0};
	u8 i;
	DHT11_Sends_Start();
	if (!DHT11_Sends_Response()) return DHT11_READ_TIMEOUT;
	for(i = 0; i < 5u; i++)
	{
		if (!DHT11_Read_Byte(&DATA[i])) return DHT11_READ_TIMEOUT;
	}
	if ((u8)(DATA[0] + DATA[1] + DATA[2] + DATA[3]) != DATA[4] ||
	    DATA[0] >= 100u || DATA[2] >= 100u)
	{
		return DHT11_READ_CHECKSUM;
	}
	*humi = DATA[0];
	*temp = DATA[2];
	return DHT11_READ_OK;
}
