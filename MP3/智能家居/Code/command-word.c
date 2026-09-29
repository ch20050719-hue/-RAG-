/**
 * @brief 语音识别事件钩子，语音模块输出识别结果时会调用此函数
 * 
 */
    uint16_t cmd_id = cmd_info_get_command_id(cmd_handle);
    uint16_t uart_cmd_id = 0;

    /* 将新版 cmd_003..cmd_014 转成设备固件使用的命令码。 */
    switch (cmd_id) {
        case 3:  uart_cmd_id = 0x01; break; /* 开灯 */
        case 4:  uart_cmd_id = 0x02; break; /* 关灯 */
        case 5:  uart_cmd_id = 0x03; break; /* 开风扇 */
        case 6:  uart_cmd_id = 0x04; break; /* 关风扇 */
        case 7:  uart_cmd_id = 0x05; break; /* 开窗 */
        case 8:  uart_cmd_id = 0x06; break; /* 关窗 */
        case 9:  uart_cmd_id = 0x07; break; /* 手动模式 */
        case 10: uart_cmd_id = 0x08; break; /* 自动模式 */
        case 11: uart_cmd_id = 0x0C; break; /* 离家：当前STM32固件定义为0x0C */
        case 12: uart_cmd_id = 0x0B; break; /* 睡眠：当前STM32固件定义为0x0B */
        case 13: uart_cmd_id = 0x09; break; /* 开门 */
        case 14: uart_cmd_id = 0x0A; break; /* 关门 */
        default: break; /* 唤醒词和未知命令不发送控制帧 */
    }

    if (uart_cmd_id != 0) {
        vmup_port_send_char(VMUP_MSG_HEAD_LOW);
        vmup_port_send_char(VMUP_MSG_HEAD_HIGH);
        vmup_port_send_char(uart_cmd_id);
        vmup_port_send_char(VMUP_MSG_TAIL);
    }
