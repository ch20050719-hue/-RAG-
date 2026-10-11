#ifndef TEST_USART_STDIO_H
#define TEST_USART_STDIO_H
/* Keil declares __FILE in usart.c; avoid conflicting with host CRT FILE. */
typedef struct __FILE FILE;
int puts(const char *text);
#endif
