#ifndef __USART_H
#define __USART_H
#include "stdio.h"	
#include "environment_protocol.h"
#include "sys.h" 

#define USART_REC_LEN  			200  	//定义最大接收字节数 200
#define EN_USART1_RX 			1		//使能（1）/禁止（0）串口1接收
	  	
extern u8  USART_RX_BUF[USART_REC_LEN]; //接收缓冲,最大USART_REC_LEN个字节.末字节为换行符 
extern u16 USART_RX_STA;  
       		//接收状态标记	
//如果想串口中断接收，请不要注释以下宏定义

/* Saturating counters since boot. port is the physical USART number: 1 or 3. */
typedef struct {
    uint16_t received_bytes;
    uint16_t overrun_count;
    uint16_t framing_count;
    uint16_t noise_count;
    uint16_t parity_count;
    uint16_t queue_overflow_count;
    uint16_t expired_count;
    uint8_t queued_commands;
} USART_ControlDiagnostics;
uint8_t USART_GetControlDiagnostics(uint8_t port, USART_ControlDiagnostics *out);
uint8_t USART1_TakeCommand(uint8_t *command);
void uart1_init(u32 bound);
void uart2_init(u32 bound);
void uart3_init(u32 bound);
uint8_t USART3_PublishEnvironment(const EnvironmentSnapshot *snapshot);
#endif


