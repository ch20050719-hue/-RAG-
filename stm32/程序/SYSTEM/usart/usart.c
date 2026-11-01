#include "sys.h"
#include "usart.h"
#include "voice_command.h"
#include "TIM3.h"
#include "gizwits_product.h" 
#include <stdio.h>



// 定义几个变量来存数据
/* Each UART owns its parser and FIFO; bytes from different links never mix. */
static volatile VoiceCommandState voice_commands[2] = {{0}};
static uint8_t next_command_source = 0u;
static volatile USART_ControlDiagnostics control_diagnostics[2] = {{0}};
static uint8_t environment_tx[ENVIRONMENT_FRAME_SIZE];
static volatile uint8_t environment_tx_position = 0u;
static volatile uint8_t environment_tx_busy = 0u;



#if 1
#pragma import(__use_no_semihosting)             
//标准库需要的支持函数                 
struct __FILE 
{ 
	int handle; 

}; 

FILE __stdout;       
//定义_sys_exit()以避免使用半主机模式    
void _sys_exit(int x) 
{ 
	x = x; 
} 
//重定义fputc函数 
int fputc(int ch, FILE *f)
{      
	while((USART1->SR&0X40)==0);//循环发送,直到发送完毕   
    USART1->DR = (u8) ch;      
	return ch;
}
#endif 

 
#if EN_USART1_RX   //如果使能了接收
//串口1中断服务程序
//注意,读取USARTx->SR能避免莫名其妙的错误   	
u8 USART_RX_BUF[USART_REC_LEN];     //接收缓冲,最大USART_REC_LEN个字节.
//接收状态
//bit15，	接收完成标志
//bit14，	接收到0x0d
//bit13~0，	接收到的有效字节数目
u16 USART_RX_STA=0;       //接收状态标记	  
  
void uart1_init(u32 bound){
  //GPIO端口设置
  GPIO_InitTypeDef GPIO_InitStructure;
	USART_InitTypeDef USART_InitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;
	 
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1|RCC_APB2Periph_GPIOA, ENABLE);	//使能USART1，GPIOA时钟
  
	//USART1_TX   GPIOA.9
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_9; //PA.9
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;	//复用推挽输出
  GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化GPIOA.9
   
  //USART1_RX	  GPIOA.10初始化
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_10;//PA10
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;//浮空输入
  GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化GPIOA.10  

  //Usart1 NVIC 配置
  NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority=0 ;//抢占优先级3
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 3;		//子优先级3
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;			//IRQ通道使能
	NVIC_Init(&NVIC_InitStructure);	//根据指定的参数初始化VIC寄存器
  
   //USART 初始化设置

	USART_InitStructure.USART_BaudRate = bound;//串口波特率
	USART_InitStructure.USART_WordLength = USART_WordLength_8b;//字长为8位数据格式
	USART_InitStructure.USART_StopBits = USART_StopBits_1;//一个停止位
	USART_InitStructure.USART_Parity = USART_Parity_No;//无奇偶校验位
	USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//无硬件数据流控制
	USART_InitStructure.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;	//收发模式

  USART_Init(USART1, &USART_InitStructure); //初始化串口1
  USART_ITConfig(USART1, USART_IT_ERR, ENABLE);
  USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);//开启串口接受中断
  USART_Cmd(USART1, ENABLE);                    //使能串口1 

}

void uart2_init(u32 bound){
  //GPIO端口设置
  GPIO_InitTypeDef GPIO_InitStructure;
	USART_InitTypeDef USART_InitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;
	 
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART2, ENABLE);	//使能USART2，GPIOA时钟
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
  
	//USART1_TX   GPIOA.9
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_2; //PA.9
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;	//复用推挽输出
  GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化GPIOA.9
   
  //USART1_RX	  GPIOA.10初始化
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_3;//PA10
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;//浮空输入
  GPIO_Init(GPIOA, &GPIO_InitStructure);//初始化GPIOA.10  

  //Usart1 NVIC 配置
  NVIC_InitStructure.NVIC_IRQChannel = USART2_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority=0 ;//抢占优先级3
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 2;		//子优先级3
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;			//IRQ通道使能
	NVIC_Init(&NVIC_InitStructure);	//根据指定的参数初始化VIC寄存器
  
   //USART 初始化设置

	USART_InitStructure.USART_BaudRate = bound;//串口波特率
	USART_InitStructure.USART_WordLength = USART_WordLength_8b;//字长为8位数据格式
	USART_InitStructure.USART_StopBits = USART_StopBits_1;//一个停止位
	USART_InitStructure.USART_Parity = USART_Parity_No;//无奇偶校验位
	USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//无硬件数据流控制
	USART_InitStructure.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;	//收发模式

  USART_Init(USART2, &USART_InitStructure); //初始化串口1
  USART_ITConfig(USART2, USART_IT_RXNE, ENABLE);//开启串口接受中断
  USART_Cmd(USART2, ENABLE);                    //使能串口1 

}
////串口中断
/* SR must be sampled before DR to clear F1 receive error flags. */
static void USART_ReceiveControl(USART_TypeDef *uart, uint8_t source)
{
    uint32_t status = uart->SR;
    uint32_t errors = status & (USART_FLAG_ORE | USART_FLAG_FE |
                                USART_FLAG_NE | USART_FLAG_PE);
    uint8_t byte;
    volatile USART_ControlDiagnostics *stats = &control_diagnostics[source];
    if ((status & USART_FLAG_RXNE) == 0u && errors == 0u) return;
    byte = (uint8_t)USART_ReceiveData(uart);
    if (errors != 0u) {
        if ((errors & USART_FLAG_ORE) && stats->overrun_count != UINT16_MAX)
            stats->overrun_count++;
        if ((errors & USART_FLAG_FE) && stats->framing_count != UINT16_MAX)
            stats->framing_count++;
        if ((errors & USART_FLAG_NE) && stats->noise_count != UINT16_MAX)
            stats->noise_count++;
        if ((errors & USART_FLAG_PE) && stats->parity_count != UINT16_MAX)
            stats->parity_count++;
        /* A damaged byte invalidates only the partial frame, never the FIFO. */
        voice_commands[source].frame_state = 0u;
        return;
    }
    if (stats->received_bytes != UINT16_MAX) stats->received_bytes++;
    VoiceCommand_ReceiveByte(&voice_commands[source], byte, g_tim3_heartbeat);
}

uint8_t USART_GetControlDiagnostics(uint8_t port, USART_ControlDiagnostics *out)
{
    uint8_t source;
    uint32_t primask;
    if (out == 0 || (port != 1u && port != 3u)) return 0u;
    source = port == 1u ? 0u : 1u;
    primask = __get_PRIMASK();
    __disable_irq();
    *out = control_diagnostics[source];
    out->queue_overflow_count = voice_commands[source].overflow_count;
    out->expired_count = voice_commands[source].expired_count;
    out->queued_commands = voice_commands[source].count;
    __set_PRIMASK(primask);
    return 1u;
}
void USART1_IRQHandler(void)
{
    USART_ReceiveControl(USART1, 0u);
}

void uart3_init(u32 bound)
{
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef usart;
    NVIC_InitTypeDef nvic;

    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);
    /* Default USART3 mapping: PB10 TX, PB11 RX (ESP32 IO18/IO17). */
    gpio.GPIO_Pin = GPIO_Pin_10;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOB, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_11;
    gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOB, &gpio);

    nvic.NVIC_IRQChannel = USART3_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;
    nvic.NVIC_IRQChannelSubPriority = 3;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);

    usart.USART_BaudRate = bound;
    usart.USART_WordLength = USART_WordLength_8b;
    usart.USART_StopBits = USART_StopBits_1;
    usart.USART_Parity = USART_Parity_No;
    usart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    usart.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART3, &usart);
    environment_tx_busy = 0u;
    environment_tx_position = 0u;
    USART_ITConfig(USART3, USART_IT_TXE, DISABLE);
    USART_ITConfig(USART3, USART_IT_ERR, ENABLE);
    USART_ITConfig(USART3, USART_IT_RXNE, ENABLE);
    USART_Cmd(USART3, ENABLE);
}

/* One owned frame at a time; TXE drains it without foreground waiting. */
uint8_t USART3_PublishEnvironment(const EnvironmentSnapshot *snapshot)
{
    uint8_t encoded[ENVIRONMENT_FRAME_SIZE];
    uint8_t i;
    uint32_t primask;
    if (!Environment_Encode(snapshot, encoded)) return 0u;
    primask = __get_PRIMASK();
    __disable_irq();
    if (environment_tx_busy) {
        __set_PRIMASK(primask);
        return 0u;
    }
    for (i = 0u; i < ENVIRONMENT_FRAME_SIZE; ++i) environment_tx[i] = encoded[i];
    environment_tx_position = 0u;
    environment_tx_busy = 1u;
    USART_ITConfig(USART3, USART_IT_TXE, ENABLE);
    __set_PRIMASK(primask);
    return 1u;
}
void USART3_IRQHandler(void)
{
    USART_ReceiveControl(USART3, 1u);
    if (USART_GetITStatus(USART3, USART_IT_TXE) != RESET)
    {
        if (environment_tx_busy) {
            USART_SendData(USART3, environment_tx[environment_tx_position++]);
            if (environment_tx_position == ENVIRONMENT_FRAME_SIZE) {
                USART_ITConfig(USART3, USART_IT_TXE, DISABLE);
                environment_tx_busy = 0u;
            }
        } else {
            USART_ITConfig(USART3, USART_IT_TXE, DISABLE);
        }
    }
}

/* Compatibility entry point for HomeControl_Process: fairly poll both UARTs. */
uint8_t USART1_TakeCommand(uint8_t *command)
{
    uint8_t found;
    uint8_t source;
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    source = next_command_source;
    found = VoiceCommand_Take(&voice_commands[source], g_tim3_heartbeat, command);
    if (!found) {
        source ^= 1u;
        found = VoiceCommand_Take(&voice_commands[source], g_tim3_heartbeat, command);
    }
    if (found) next_command_source = (uint8_t)(source ^ 1u);
    __set_PRIMASK(primask);
    return found;
}

void USART2_IRQHandler(void)                	//串口2中断服务程序
{
		u8 Res;
		if(USART_GetITStatus(USART2, USART_IT_RXNE) != RESET)  //接收中断(接收到的数据必须是0x0d 0x0a结尾)
		{
				Res =USART_ReceiveData(USART2);	//读取接收到的数据	
			
				gizPutData(&Res,1);
		} 
} 
#endif	

