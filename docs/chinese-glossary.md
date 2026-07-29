# Chinese Glossary for Mictuning (Qunchen) Codebase

Translations of Chinese strings found in the decompiled source and logcat output.

## Common terms

| Chinese | Pinyin | English | Context |
|---------|--------|---------|---------|
| 普通 | pǔtōng | normal/standard | Labels the BLE code path (vs SPP) |
| 开关 | kāiguān | switch / on-off | On/off state in F1 response parsing |
| 查询 | cháxún | query | Labels status query calls |
| 写入 | xiěrù | write | Labels data write operations |
| 蓝牙 | lányá | Bluetooth | General Bluetooth reference |
| 连接 | liánjiē | connect/connection | Connection state |
| 断开 | duànkāi | disconnect | Disconnection events |
| 搜索 | sōusuǒ | search | Device discovery |
| 扫描 | sǎomiáo | scan | BLE scanning |
| 模式 | móshì | mode | Operating mode |
| 通知 | tōngzhī | notification | BLE characteristic notifications |

## Log messages — SPPManager.java

| Chinese | English | Location |
|---------|---------|----------|
| 主动断开 | Active disconnect (app-initiated) | line 121 |
| 移除了！！ | Removed!! | lines 131, 138, 147 |
| 不存在连接记录，则不进行重连 | No connection record, don't reconnect | line 216 |
| 超过最大连接次数 | Exceeded max connection attempts | line 219 |
| 重新连接 | Reconnecting | line 222 |
| 不存在连接记录，则直接断开 | No connection record, disconnect directly | line 248 |
| spp写入失败》》btSocket==null | SPP write failed — btSocket is null | line 262 |
| spp写入失败》》outputStream==null | SPP write failed — outputStream is null | line 266 |
| spp写入 | SPP write | line 282 |
| 根本没有 | Doesn't exist at all | line 311 |
| 开始搜索 | Starting search | line 352 |
| 搜索结束 | Search ended | line 356 |
| 是否为主线程 | Is it the main thread? | line 378 |
| 开始连接 | Starting connection | line 454 |
| 连接成功 | Connection successful | line 458 |
| 获取到了吗？ | Did we get it? | line 472 |
| 开关 | Switch (on/off) | line 476 |
| 已经断开SPP | SPP already disconnected | line 496 |
| 蓝牙已断开连接 | Bluetooth disconnected | line 497 |
| 蓝牙连接结束 | Bluetooth connection ended | line 502 |

## Log messages — ControlUtil.java

| Chinese | English | Location |
|---------|---------|----------|
| 连接成功 | Connection successful | line 111 |
| 开始扫描 | Starting scan | line 319 |
| 模式不匹配，过滤 | Mode mismatch, filtering out | line 346 |
| P2C开启通知成功，查询状态 | P2C notification enabled, querying status | line 636 |
| 开启notify失败 | Failed to enable notify | line 642 |
| openValue开关 | Open-value switch (on/off state) | line 676 |
| 普通 | Normal (BLE mode) | lines 492, 505, 760, 785 |
| 最后的 | Final/last (value) | line 946 |
| 正在重连设备 | Reconnecting device | line 1477 |
| 不是当前 | Not the current (device) | connectControl inner class |
| 重连成功 | Reconnection successful | reConnectDevice inner class |

## Log messages — logcat capture

| Chinese | English | Context |
|---------|---------|---------|
| 看看有没有被我覆盖！！ | Let me check if I've been overwritten!! | Broadcast receiver registration debug msg |
| onOffEvent????setOnOff | (mixed) Setting on/off state | On/off event handler |

## Symbols used as decoration

| Symbol | Meaning |
|--------|---------|
| 》》 | ≈ `>>` — used as visual separator in log messages |
| ！！ | ≈ `!!` — emphasis |
