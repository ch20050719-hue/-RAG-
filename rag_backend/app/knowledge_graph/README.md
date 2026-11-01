# 智能家居知识图谱

知识图谱只服务于智能家居设备、房间、传感器、场景、安全规则、动作、状态和通信技术。

实体类型：`DEVICE`、`SENSOR`、`ROOM`、`SCENARIO`、`SAFETY_RULE`、`ACTION`、`STATE`、`TECHNOLOGY`、`LOCATION`、`DATE_PERIOD`。

关系类型：`DEVICE_IN_ROOM`、`SENSOR_IN_ROOM`、`SUPPORTS_ACTION`、`TRIGGERS`、`REQUIRES_SAFETY`、`REPORTS_STATE`、`CONNECTED_BY`、`RELATED_TO`。

写入图谱前必须执行实体类型白名单校验、租户隔离和安全规则检查；设备控制仍必须经设备工具与安全策略，图谱只提供可追溯的知识关联，不直接下发底层指令。
