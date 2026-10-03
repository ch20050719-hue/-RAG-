#include <assert.h>
#include <stdint.h>
#include <string.h>

#include "../Gizwits/gizwits_protocol.c"

static uint32_t fakeTime;
static int32_t fakeUartResult;
uint32_t gizGetTimerCount(void) { return fakeTime; }
int32_t uartWrite(uint8_t *buf, uint32_t len) { (void)buf; (void)len; return fakeUartResult; }
uint8_t gizProtocolSum(uint8_t *buf, uint32_t len) { (void)buf; (void)len; return 0; }
uint16_t exchangeBytes(uint16_t value) { return (uint16_t)((value << 8) | (value >> 8)); }
uint32_t exchangeWord(uint32_t value) { return value; }
uint32_t gizY2X(uint32_t ratio, int32_t addition, int32_t value)
{
    return (uint32_t)((value - addition) / (int32_t)ratio);
}
int32_t gizVarlenCompressValue(uint32_t offset, uint32_t bits, uint8_t *buf, uint32_t value)
{
    (void)bits;
    buf[offset / 8] |= (uint8_t)(value << (offset % 8));
    return 0;
}
int8_t rbCreate(rb_t *rb) { (void)rb; return 0; }
int32_t rbCanRead(rb_t *rb) { (void)rb; return 0; }
int32_t rbRead(rb_t *rb, void *data, size_t count)
{ (void)rb; (void)data; (void)count; return 0; }
int32_t rbWrite(rb_t *rb, const void *data, size_t count)
{ (void)rb; (void)data; return (int32_t)count; }
void mcuRestart(void) { }
int8_t gizwitsEventProcess(eventInfo_t *info, uint8_t *data, uint32_t len)
{ (void)info; (void)data; (void)len; return 0; }

/* Exercise the production decoder with the same bit and ratio rules as the utility layer. */
int8_t gizByteOrderExchange(uint8_t *buf, uint32_t len)
{
    uint32_t i;
    for(i = 0; i < len / 2; i++)
    {
        uint8_t value = buf[i];
        buf[i] = buf[len - 1 - i];
        buf[len - 1 - i] = value;
    }
    return 0;
}
int32_t gizVarlenDecompressionValue(uint32_t offset, uint32_t bits, uint8_t *array, uint32_t len)
{
    (void)bits;
    assert(len > offset / 8);
    return (array[offset / 8] >> (offset % 8)) & 1;
}
int32_t gizX2Y(uint32_t ratio, int32_t addition, uint32_t value)
{
    return (int32_t)(value * ratio) + addition;
}

int main(void)
{
    dataPointFlags_t flags = {0};
    dataPoint_t decoded = {0}, last = {0}, current = {0};
    eventInfo_t info = {0};
    protocolHead_t head;
    uint8_t data[DATAPOINT_FLAG_LEN + 3];
    uint8_t report[32] = {0};
    uint32_t reportLen = 0;

    flags.flagFan = 1;
    flags.flagCurtain = 1;
    flags.flagSystem_Mode = 1;
    flags.flagset_light = 1;
    flags.flagSmoke_Threshold = 1;
    memcpy(data, &flags, DATAPOINT_FLAG_LEN);
    gizByteOrderExchange(data, DATAPOINT_FLAG_LEN);
    data[DATAPOINT_FLAG_LEN] = 0x03;
    data[DATAPOINT_FLAG_LEN + 1] = 200;
    data[DATAPOINT_FLAG_LEN + 2] = 150;
    assert(gizDataPoint2Event(data, sizeof(data), &info, &decoded) == 0);
    assert(info.num == 5);
    assert(info.event[0] == EVENT_Fan && decoded.valueFan == 1);
    assert(info.event[1] == EVENT_Curtain && decoded.valueCurtain == 1);
    assert(info.event[2] == EVENT_System_Mode && decoded.valueSystem_Mode == 0);
    assert(info.event[3] == EVENT_set_light && decoded.valueset_light == 2000);
    assert(info.event[4] == EVENT_Smoke_Threshold && decoded.valueSmoke_Threshold == 1500);

    info.num = 0;
    assert(gizDataPoint2Event(data, sizeof(data) - 1, &info, &decoded) == -1);
    assert(gizDataPoint2Event(data, DATAPOINT_FLAG_LEN - 1, &info, &decoded) == -1);

    current.valueset_humi = 80;
    current.valueset_light = 2000;
    current.valueSmoke_Threshold = 1500;
    fakeTime = REPORT_TIME_MAX;
    assert(gizCheckReport(&current, &last) == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagset_humi == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagset_light == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagSmoke_Threshold == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagset_temp == 0);
    memset(&gizwitsProtocol.waitReportDatapointFlag, 0, DATAPOINT_FLAG_LEN);
    gizwitsProtocol.waitReportDatapointFlag.flagset_light = 1;
    gizwitsProtocol.waitReportDatapointFlag.flagSmoke_Threshold = 1;
    assert(gizDataPoints2ReportData(&current, report, &reportLen) == 0);
    assert(reportLen == DATAPOINT_FLAG_LEN + 2);
    assert(report[DATAPOINT_FLAG_LEN] == 200);
    assert(report[DATAPOINT_FLAG_LEN + 1] == 150);
    assert(gizProtocolHeadInit(&head) == 0);
    assert(head.head[0] == 0xFF && head.head[1] == 0xFF);
    fakeUartResult = -2;
    assert(gizwitsSetMode(WIFI_SOFTAP_MODE) == -2);
    assert(gizwitsProtocol.waitAck.flag == 0);
    return 0;
}
