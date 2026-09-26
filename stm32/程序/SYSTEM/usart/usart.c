#include "sys.h"
#include "usart.h"	
#include "gizwits_product.h" 
#include <stdio.h>



// 定义几个变量来存数据
uint8_t voice_data[50];  // 存4个字节：F4 06 命令 FB
uint8_t data_count = 0; // 记录收到了第几个数据
volatile uint8_t new_cmd = 0;    // 收到新命令的标志
volatile uint8_t cmd_value = 0;  // 命令值



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
//void USART1_IRQHandler(void)
//{
//    if(USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
//    {
//        // 1. 读取当前收到的这一个字节
//        uint8_t one_byte = USART_ReceiveData(USART1);
//        
//        // 2. 安全写入：防止数组越界
//        if(data_count < 4)  // 增加边界检查
//        {
//            voice_data[data_count] = one_byte;
//            data_count++;
//        }
//        else
//        {
//            // 如果data_count异常，强制重置
//            data_count = 0;
//        }
//        
//        // 3. 如果收齐了4个字节
//        if(data_count >= 4)
//        {
//            // 检查格式是否正确：F4开头，FB结尾
//            if(voice_data[0] == 0xF4 && voice_data[3] == 0xFB)
//            {
//                cmd_value = voice_data[2];  // 第3个字节是命令
//                new_cmd = 1;  // 设置新命令标志
//            }
//            
//            // 重置计数，准备接收下一组数据
//            data_count = 0;
//            
//            // 可选：清除缓冲区，防止残留数据干扰
//            memset(voice_data, 0, sizeof(voice_data));
//        }
//        
//        // 清除中断标志
//        USART_ClearITPendingBit(USART1, USART_IT_RXNE);
//    }
//}
// 改进的串口中断处理
void USART1_IRQHandler(void)
{
    static uint8_t sync_state = 0;  // 同步状态：0=寻找帧头，1=接收数据
    
    if(USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
    {
        uint8_t one_byte = USART_ReceiveData(USART1);
        
        switch(sync_state)
        {
            case 0:  // 寻找帧头状态
                if(one_byte == 0xF4)  // 找到帧头
                {
                    voice_data[0] = one_byte;
                    data_count = 1;
                    sync_state = 1;  // 切换到接收数据状态
                }
                // 不是0xF4就丢弃，继续寻找
                break;
                
            case 1:  // 接收数据状态
                if(data_count < 4)
                {
                    voice_data[data_count] = one_byte;
                    data_count++;
                }
                
                if(data_count >= 4)
                {
                    // 检查帧尾是否正确
                    if(voice_data[3] == 0xFB)
                    {
                        cmd_value = voice_data[2];  // 有效命令
                        new_cmd = 1;
                    }
                    
                    // 无论帧尾是否正确，都重置状态
                    data_count = 0;
                    sync_state = 0;  // 返回寻找帧头状态
                    
                    // 可选：清空缓冲区
                    memset(voice_data, 0, 4);
                }
                break;
        }
        
        // 清除中断标志
        USART_ClearITPendingBit(USART1, USART_IT_RXNE);
    }
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

