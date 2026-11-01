#include <assert.h>
#include <stdint.h>
#include <string.h>

#include "stubs/gizwits_credentials.h"
#include "../Gizwits/gizwits_protocol.c"
#include "../Utils/ringBuffer.c"
#include "../Utils/common.c"

static uint32_t fakeTime;
static int32_t fakeUartResult;
static unsigned uartCalls;
static uint8_t lastTx[RB_MAX_LEN];
static uint32_t lastTxLen;
static unsigned lightEvents;
static uint8_t hardwareLight;
uint32_t gizGetTimerCount(void) { return fakeTime; }
int32_t uartWrite(uint8_t *buf, uint32_t len)
{
    assert(len <= sizeof(lastTx));
    memcpy(lastTx, buf, len);
    lastTxLen = len;
    uartCalls++;
    return fakeUartResult ? fakeUartResult : (int32_t)len;
}
uint32_t gizY2X(uint32_t ratio, int32_t addition, int32_t value)
{
    return (uint32_t)((value - addition) / (int32_t)ratio);
}
int32_t gizVarlenCompressValue(uint32_t offset, uint32_t bits, uint8_t *buf, uint32_t value)
{
    uint32_t bit;
    for(bit = 0; bit < bits; bit++)
    {
        if(value & (1u << bit))
            buf[(offset + bit) / 8] |= (uint8_t)(1u << ((offset + bit) % 8));
    }
    return 0;
}
void mcuRestart(void) { }
int8_t gizwitsEventProcess(eventInfo_t *info, uint8_t *data, uint32_t len)
{
    unsigned i;
    (void)len;
    for(i = 0; i < info->num; i++)
        if(info->event[i] == EVENT_Light)
        {
            lightEvents++;
            hardwareLight = ((dataPoint_t *)data)->valueLight;
        }
    return 0;
}

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
    uint32_t bit;
    int32_t value = 0;
    for(bit = 0; bit < bits; bit++)
    {
        assert((offset + bit) / 8 < len);
        if(array[(offset + bit) / 8] & (uint8_t)(1u << ((offset + bit) % 8)))
            value |= (int32_t)(1u << bit);
    }
    return value;
}
int32_t gizX2Y(uint32_t ratio, int32_t addition, uint32_t value)
{
    return (int32_t)(value * ratio) + addition;
}

static void testReportPolicy(void)
{
    dataPoint_t current = {0};
    fakeTime = 0;
    fakeUartResult = 0;
    uartCalls = 0;
    gizwitsInit();
    fakeTime = 599999;
    gizDevReportPolicy(&current);
    assert(uartCalls == 0);
    fakeTime = 600001;
    current.valueLight = 1;
    gizDevReportPolicy(&current);
    assert(uartCalls == 1); /* Periodic and change share one ACK slot. */
    assert(gizwitsProtocol.reportDataLen > DATAPOINT_FLAG_LEN + 1);
    current.valueFan = 1;
    gizDevReportPolicy(&current);
    assert(uartCalls == 1); /* Do not overwrite an outstanding report. */
    gizwitsProtocol.waitAck.flag = 0;
    gizDevReportPolicy(&current);
    assert(uartCalls == 2);

    fakeTime = 0;
    gizwitsInit();
    memset(&current, 0, sizeof(current));
    uartCalls = 0;
    fakeTime = 1000;
    current.valuetemp = 25;
    current.valuehumi = 60;
    current.valueLight_intensity = 1000;
    current.valueSmmmoke = 500;
    current.valueLight = 1;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valuetemp == 0);
    assert(gizwitsProtocol.gizLastDataPoint.valuehumi == 0);
    assert(gizwitsProtocol.gizLastDataPoint.valueLight_intensity == 0);
    assert(gizwitsProtocol.gizLastDataPoint.valueSmmmoke == 0);
    assert(gizwitsProtocol.gizLastDataPoint.valueLight == 1);
    gizwitsProtocol.waitAck.flag = 0;
    fakeTime = REPORT_TIME_MAX - 1;
    current.valueFan = 1;
    gizDevReportPolicy(&current);
    gizwitsProtocol.waitAck.flag = 0;
    fakeTime = REPORT_TIME_MAX;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valuetemp == 25);
    assert(gizwitsProtocol.gizLastDataPoint.valuehumi == 60);
    assert(gizwitsProtocol.gizLastDataPoint.valueLight_intensity == 1000);
    assert(gizwitsProtocol.gizLastDataPoint.valueSmmmoke == 500);
    assert(uartCalls == 3); /* Frequent commands must not starve sensors. */

    gizwitsProtocol.waitAck.flag = 0;
    current.valueLight = 0;
    fakeUartResult = -1;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valueLight == 1);
    assert(gizwitsProtocol.waitAck.flag == 0);
    fakeUartResult = 1; /* A short UART write is also a failure. */
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valueLight == 1);
    fakeUartResult = 0;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valueLight == 0);

    gizwitsProtocol.waitAck.flag = 0;
    current.valueHome_Scene = Home_Scene_VALUE_MAX;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.waitAck.flag == 0);
    assert(gizwitsProtocol.gizLastDataPoint.valueHome_Scene == 0);
    current.valueHome_Scene = Home_Scene_VALUE1;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valueHome_Scene == Home_Scene_VALUE1);

    gizwitsProtocol.waitAck.flag = 0;
    fakeTime += REPORT_TIME_MAX;
    current.valuetemp = 26;
    fakeUartResult = -1;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valuetemp == 25);
    fakeUartResult = 0;
    gizDevReportPolicy(&current);
    assert(gizwitsProtocol.gizLastDataPoint.valuetemp == 26);

    fakeTime = UINT32_MAX - 100;
    gizwitsInit();
    memset(&current, 0, sizeof(current));
    uartCalls = 0;
    gizDevReportPolicy(&current);
    assert(uartCalls == 0); /* Reinitialization starts a fresh interval. */
    fakeTime += 600001u;
    fakeUartResult = -1;
    gizDevReportPolicy(&current);
    assert(uartCalls == 1);
    fakeUartResult = 0;
    fakeTime++;
    gizDevReportPolicy(&current);
    assert(uartCalls == 2); /* Failed periodic reports remain due. */
    gizwitsProtocol.waitAck.flag = 0;
    gizDevReportPolicy(&current);
    assert(uartCalls == 2);
}

static void testAckTimeoutRecovery(void)
{
    dataPoint_t current = {0};
    fakeTime = 100u;
    fakeUartResult = 0;
    uartCalls = 0;
    gizwitsInit();
    current.valueLight = 1u;
    gizDevReportPolicy(&current);
    assert(uartCalls == 1u && gizwitsProtocol.waitAck.flag);
    assert(gizwitsSetMode(WIFI_SOFTAP_MODE) == -3);
    assert(uartCalls == 1u && gizwitsProtocol.waitAck.buf[4] == CMD_REPORT_P0);
    gizwitsProtocol.waitAck.num = SEND_MAX_NUM;
    gizProtocolAckHandle();
    assert(gizwitsProtocol.waitAck.flag); /* Last retransmission still gets an ACK window. */
    fakeTime += SEND_MAX_TIME + 1u;
    gizProtocolAckHandle();
    assert(!gizwitsProtocol.waitAck.flag);
    fakeTime += REPORT_TIME_MAX - 1u;
    gizDevReportPolicy(&current);
    assert(uartCalls == 1u);
    fakeTime++;
    gizDevReportPolicy(&current);
    assert(uartCalls == 2u);
    assert(gizwitsProtocol.reportDataLen == 14u);
}

static void testProvisionPriority(void)
{
    dataPoint_t current = {0};
    unsigned before;
    fakeTime = 0u;
    fakeUartResult = 0;
    gizwitsInit();
    current.valueLight = 1u;
    gizDevReportPolicy(&current);
    before = uartCalls;
    gizwitsPauseReporting(1u);
    assert(gizwitsSetMode(WIFI_AIRLINK_MODE) == -3);
    /* An ACK arrives while the device continues changing. Reports yield the slot. */
    gizwitsProtocol.waitAck.flag = 0u;
    current.valueFan = 1u;
    fakeTime += REPORT_TIME_MAX;
    gizDevReportPolicy(&current);
    assert(uartCalls == before);
    assert(gizwitsSetMode(WIFI_AIRLINK_MODE) >= 0);
    assert(uartCalls == before + 1u);
    assert(gizwitsProtocol.waitAck.buf[4] == CMD_WIFI_CONFIG);
    gizwitsPauseReporting(0u);
    gizDevReportPolicy(&current);
    assert(uartCalls == before + 1u); /* Provisioning ACK retains its slot. */
    gizwitsProtocol.waitAck.flag = 0u;
    gizDevReportPolicy(&current);
    assert(uartCalls == before + 2u);
    assert(gizwitsProtocol.gizLastDataPoint.valueFan == 1u);
}

static unsigned remoteFailures;
#define CHECK_REMOTE(condition, message) do { \
    if(!(condition)) { printf("FAIL: %s\n", message); remoteFailures++; } \
} while(0)

/* Feed the actual UART entry point, including FF escaping and the real checksum. */
static void feedWire(const uint8_t *packet, size_t length)
{
    size_t i;
    for(i = 0; i < length; i++)
    {
        uint8_t byte = packet[i];
        assert(gizPutData(&byte, 1u) == 1);
        if(i >= 2u && byte == 0xFFu)
        {
            byte = 0x55u;
            assert(gizPutData(&byte, 1u) == 1);
        }
    }
}

static void feedPacket(uint8_t command, uint8_t sn, const uint8_t *payload, size_t length)
{
    uint8_t packet[MAX_PACKAGE_LEN] = {0xFFu, 0xFFu};
    size_t total = sizeof(protocolHead_t) + length + 1u;
    assert(total < sizeof(packet));
    packet[3] = (uint8_t)(total - 4u);
    packet[4] = command;
    packet[5] = sn;
    if(length) memcpy(packet + sizeof(protocolHead_t), payload, length);
    packet[total - 1u] = gizProtocolSum(packet, (uint32_t)total);
    feedWire(packet, total);
}

static void resetRemote(void)
{
    fakeTime = 0u;
    fakeUartResult = 0;
    uartCalls = lightEvents = 0u;
    hardwareLight = 0u;
    lastTxLen = 0u;
    gizwitsInit();
    gizwitsPauseReporting(1u);
}

static void testShortPackets(void)
{
    const uint8_t control[] = {ACTION_CONTROL_DEVICE, 0u, 1u, 1u};
    const uint8_t readShort[] = {ACTION_READ_DEV_STATUS, 0u};
    dataPoint_t current = {0};
    unsigned total;
    resetRemote();
    for(total = 5u; total < sizeof(protocolCommon_t); total++)
    {
        uint8_t shortPacket[8] = {0xFFu, 0xFFu, 0u, 0u, CMD_ISSUED_P0};
        unsigned before;
        feedPacket(CMD_ISSUED_P0, 0x10u, control, sizeof(control));
        gizwitsHandle(&current);
        hardwareLight = 0u; /* Local operation occurs after the valid remote command. */
        before = lightEvents;
        shortPacket[3] = (uint8_t)(total - 4u);
        shortPacket[total - 1u] = gizProtocolSum(shortPacket, total);
        feedWire(shortPacket, total);
        gizwitsHandle(&current);
        CHECK_REMOTE(lightEvents == before && hardwareLight == 0u,
                     "short frame must not replay a previous light command");
    }
    { unsigned before = uartCalls;
      feedPacket(CMD_ISSUED_P0, 0x20u, NULL, 0u);
      gizwitsHandle(&current);
      feedPacket(CMD_ISSUED_P0, 0x21u, readShort, sizeof(readShort));
      gizwitsHandle(&current);
      CHECK_REMOTE(uartCalls == before, "missing action/query flags must not receive a successful reply"); }
    /* A rejected packet must not prevent a later valid, escaped packet. */
    feedPacket(CMD_ISSUED_P0, 0xFFu, control, sizeof(control));
    gizwitsHandle(&current);
    CHECK_REMOTE(hardwareLight == 1u && lastTx[5] == 0xFFu,
                 "valid escaped control works after rejected short packets");
}

static void testAckSequence(void)
{
    dataPoint_t current = {0};
    uint8_t sn;
    unsigned before;
    resetRemote();
    gizwitsPauseReporting(0u);
    current.valueLight = 1u;
    gizDevReportPolicy(&current);
    sn = gizwitsProtocol.waitAck.buf[5];
    feedPacket(ACK_REPORT_P0, (uint8_t)(sn + 1u), NULL, 0u);
    gizwitsHandle(&current);
    CHECK_REMOTE(gizwitsProtocol.waitAck.flag, "wrong SN ACK must keep the pending packet");
    before = uartCalls;
    fakeTime += SEND_MAX_TIME + 1u;
    gizwitsHandle(&current);
    CHECK_REMOTE(uartCalls == before + 1u && gizwitsProtocol.waitAck.buf[5] == sn,
                 "wrong SN ACK must not stop retransmission with the original SN");
    feedPacket(ACK_REPORT_P0, sn, NULL, 0u);
    gizwitsHandle(&current);
    CHECK_REMOTE(!gizwitsProtocol.waitAck.flag, "matching ACK must clear the pending packet");
    current.valueFan = 1u;
    gizDevReportPolicy(&current);
    feedPacket(ACK_REPORT_P0, sn, NULL, 0u);
    gizwitsHandle(&current);
    CHECK_REMOTE(gizwitsProtocol.waitAck.flag, "duplicate old ACK must not cancel the next report");
    sn = gizwitsProtocol.waitAck.buf[5];
    feedPacket(ACK_WIFI_CONFIG, sn, NULL, 0u);
    gizwitsHandle(&current);
    CHECK_REMOTE(gizwitsProtocol.waitAck.flag, "matching SN with wrong command must not clear a report");
    feedPacket(ACK_REPORT_P0, sn, NULL, 0u);
    gizwitsHandle(&current);
    CHECK_REMOTE(!gizwitsProtocol.waitAck.flag, "next report accepts its own ACK");
}

static void testCurrentStatusQueries(void)
{
    const uint8_t lightQuery[] = {ACTION_READ_DEV_STATUS, 0u, 1u};
    const uint8_t tempQuery[] = {ACTION_READ_DEV_STATUS, 0u, 0x80u};
    const uint8_t fullQuery[] = {ACTION_READ_DEV_STATUS, 0x7Fu, 0xFFu};
    dataPoint_t current = {0};
    resetRemote();
    /* Keep an older report pending while current controls and sensor values change. */
    gizwitsPauseReporting(0u);
    current.valueFan = 1u;
    gizDevReportPolicy(&current);
    current.valueLight = 1u;
    current.valuetemp = 26u;
    feedPacket(CMD_ISSUED_P0, 0x31u, lightQuery, sizeof(lightQuery));
    gizwitsHandle(&current);
    CHECK_REMOTE(lastTxLen == 13u && exchangeBytes(((protocolHead_t *)lastTx)->len) == 9u,
                 "single-light query response uses its serialized length");
    CHECK_REMOTE(lastTx[8] == ACTION_READ_DEV_STATUS_ACK && lastTx[11] == 1u,
                 "query returns the current light, not the last report snapshot");
    CHECK_REMOTE(lastTx[lastTxLen - 1u] == gizProtocolSum(lastTx, lastTxLen),
                 "query reply checksum covers its exact response");
    CHECK_REMOTE(gizwitsProtocol.gizLastDataPoint.valueLight == 0u && gizwitsProtocol.waitAck.flag,
                 "queries preserve the pending report and its change-detection snapshot");
    feedPacket(CMD_ISSUED_P0, 0x32u, tempQuery, sizeof(tempQuery));
    gizwitsHandle(&current);
    CHECK_REMOTE(lastTxLen == 13u && lastTx[11] == 26u,
                 "sensor query returns the current reading before the reporting interval");
    feedPacket(CMD_ISSUED_P0, 0x33u, fullQuery, sizeof(fullQuery));
    gizwitsHandle(&current);
    CHECK_REMOTE(lastTxLen == 24u && lastTx[8] == ACTION_READ_DEV_STATUS_ACK,
                 "full query keeps the existing complete data-point format");
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

    memset(&flags, 0, sizeof(flags));
    memset(&decoded, 0, sizeof(decoded));
    memset(&info, 0, sizeof(info));
    flags.flagLight = 1;
    flags.flagSystem_Mode = 1;
    flags.flagDoor_Target = 1;
    flags.flagHome_Scene = 1;
    flags.flagset_temp = 1;
    memcpy(data, &flags, DATAPOINT_FLAG_LEN);
    gizByteOrderExchange(data, DATAPOINT_FLAG_LEN);
    /* Light=1, System_Mode=1, Door_Target=2, Home_Scene=2. */
    data[DATAPOINT_FLAG_LEN] = 0x2B;
    data[DATAPOINT_FLAG_LEN + 1] = 42;
    assert(gizDataPoint2Event(data, DATAPOINT_FLAG_LEN + 2, &info, &decoded) == 0);
    assert(info.num == 5);
    assert(info.event[0] == EVENT_Light && decoded.valueLight == 1);
    assert(info.event[1] == EVENT_System_Mode && decoded.valueSystem_Mode == 1);
    assert(info.event[2] == EVENT_Door_Target && decoded.valueDoor_Target == Door_Target_VALUE2);
    assert(info.event[3] == EVENT_Home_Scene && decoded.valueHome_Scene == Home_Scene_VALUE2);
    assert(info.event[4] == EVENT_set_temp && decoded.valueset_temp == 42);

    info.num = 0;
    assert(gizDataPoint2Event(data, DATAPOINT_FLAG_LEN + 1, &info, &decoded) == -1);
    assert(gizDataPoint2Event(data, DATAPOINT_FLAG_LEN - 1, &info, &decoded) == -1);

    current.valueset_humi = 80;
    current.valueset_light = 2000;
    current.valueSmoke_Threshold = 1500;
    current.valueDoor_Target = Door_Target_VALUE2;
    current.valueHome_Scene = Home_Scene_VALUE2;
    last.valueDoor_Target = Door_Target_VALUE1;
    last.valueHome_Scene = Home_Scene_VALUE1;
    fakeTime = REPORT_TIME_MAX;
    assert(gizCheckReport(&current, &last) == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagset_humi == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagset_light == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagSmoke_Threshold == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagset_temp == 0);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagDoor_Target == 1);
    assert(gizwitsProtocol.waitReportDatapointFlag.flagHome_Scene == 1);
    memset(&gizwitsProtocol.waitReportDatapointFlag, 0, DATAPOINT_FLAG_LEN);
    gizwitsProtocol.waitReportDatapointFlag.flagDoor_Target = 1;
    gizwitsProtocol.waitReportDatapointFlag.flagHome_Scene = 1;
    assert(gizDataPoints2ReportData(&current, report, &reportLen) == 0);
    assert(reportLen == DATAPOINT_FLAG_LEN + 1);
    assert(report[DATAPOINT_FLAG_LEN] == 0x0A);
    current.valueHome_Scene = Home_Scene_VALUE_MAX;
    gizwitsProtocol.waitReportDatapointFlag.flagHome_Scene = 1;
    assert(gizDataPoints2ReportData(&current, report, &reportLen) == -1);
    current.valueHome_Scene = Home_Scene_VALUE2;
    memset(&gizwitsProtocol.waitReportDatapointFlag, 0, DATAPOINT_FLAG_LEN);
    gizwitsProtocol.waitReportDatapointFlag.flagset_light = 1;
    gizwitsProtocol.waitReportDatapointFlag.flagSmoke_Threshold = 1;
    assert(gizDataPoints2ReportData(&current, report, &reportLen) == 0);
    assert(reportLen == DATAPOINT_FLAG_LEN + 2);
    assert(report[DATAPOINT_FLAG_LEN] == 200);
    assert(report[DATAPOINT_FLAG_LEN + 1] == 150);

    /* A full report includes nine bool/enum bits, so the scene crosses a byte. */
    {
        const uint8_t expected[] = {
            0x7F, 0xFF, 0x01, 0x57,
            25, 60, 30, 70, 123, 145, 0x03, 0xE8, 0x05, 0xDC
        };
        assert(sizeof(gizwitsElongateP0Form_t) >= sizeof(expected));
        assert(sizeof(gizwitsProtocol.reportData) >= sizeof(expected));
        memset(&flags, 0, sizeof(flags));
        flags.flagLight = flags.flagFan = flags.flagCurtain = 1;
        flags.flagSystem_Status = flags.flagSystem_Mode = 1;
        flags.flagDoor_Target = flags.flagHome_Scene = 1;
        flags.flagtemp = flags.flaghumi = 1;
        flags.flagset_temp = flags.flagset_humi = 1;
        flags.flagset_light = flags.flagSmoke_Threshold = 1;
        flags.flagLight_intensity = flags.flagSmmmoke = 1;
        current.valueLight = current.valueFan = current.valueCurtain = 1;
        current.valueSystem_Status = System_Status_VALUE0;
        current.valueSystem_Mode = System_Mode_VALUE1;
        current.valueDoor_Target = Door_Target_VALUE2;
        current.valueHome_Scene = Home_Scene_VALUE2;
        current.valuetemp = 25;
        current.valuehumi = 60;
        current.valueset_temp = 30;
        current.valueset_humi = 70;
        current.valueset_light = 1230;
        current.valueSmoke_Threshold = 1450;
        current.valueLight_intensity = 1000;
        current.valueSmmmoke = 1500;
        gizwitsProtocol.waitReportDatapointFlag = flags;
        memset(report, 0xA5, sizeof(report));
        assert(gizDataPoints2ReportData(&current, report, &reportLen) == 0);
        assert(reportLen == sizeof(expected));
        assert(memcmp(report, expected, sizeof(expected)) == 0);
        assert(report[sizeof(expected)] == 0xA5);
    }
    assert(gizProtocolHeadInit(&head) == 0);
    assert(head.head[0] == 0xFF && head.head[1] == 0xFF);
    fakeUartResult = -2;
    assert(gizwitsSetMode(WIFI_SOFTAP_MODE) == -2);
    assert(gizwitsProtocol.waitAck.flag == 0);
    testReportPolicy();
    testAckTimeoutRecovery();
    testProvisionPriority();
    testShortPackets();
    testAckSequence();
    testCurrentStatusQueries();
    printf("remote protocol regression failures: %u\n", remoteFailures);
    return remoteFailures != 0u;
}
