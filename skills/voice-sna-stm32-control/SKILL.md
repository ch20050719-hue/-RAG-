---
name: voice-sna-stm32-control
description: "Configure and troubleshoot Snaner offline voice projects (.sn/.sna) that send UART commands to STM32, including wake/TTS, command-ID mapping, and firmware validation."
---

# Voice SNA to STM32 Control

Use this skill when editing or diagnosing a Snaner voice project that recognizes offline speech and sends UART commands to an STM32. It covers the voice project, generated voice firmware, and the STM32 command path. It does not imply a DeepSeek/cloud integration or authorize hardware, wiring, power-supply, or firmware-flashing changes.

## Keep the project layers distinct

- A voice-project file (.sn or .sna) configures recognition phrases, replies, thresholds, audio, UART, and timeouts. The supported format depends on the platform version; do not rename or interchange formats.
- The voice code area (for example, Code/command-word.c) may be a platform-injected callback snippet, not a standalone C translation unit. Verify where and with what signature the platform compiles it.
- The voice module BIN is generated output. It is not the STM32 source and its timestamp does not prove that it was programmed to a chip.
- STM32 source and its Keil project are a separate firmware layer. A spoken reply proves neither that a UART frame was transmitted nor that the STM32 executed the action.

When it is unclear which layer the user means, identify the exact platform version and file before editing. For this project, the active voice project is MP3/智能家居/智能家居.sna in the repository root; the original STM32 baseline at stm32/程序原版，不要i修改 is read-only, and stm32/程序 is the working copy.

## Workflow

1. **Inspect and preserve the current state.** Read the active SNA/SN, voice callback snippets, relevant SDK hook definitions, STM32 UART parser, command dispatcher, mode/state conditions, and final actuator driver. Record file timestamps and current project status. Before changing project configuration, save a dated copy of the exact current files. Do not replace a newer user-edited SNA with an older full-project backup.

2. **Extract the actual voice configuration.** Record each phrase, its assigned command ID, aliases, confidence/threshold, reply and audio source, wake words/replies, UART port/baud/header/tail, and timeout. Treat the project’s stored IDs as authoritative; do not infer IDs from table row numbers or screenshots. Confirm the platform’s syntax for phrase alternatives before editing separators such as |.

3. **Verify callback integration in the installed SDK.** Read the real hook declarations and call sites. Establish whether the platform inserts the Code snippet into sys_asr_result_hook, snr_asr_result_hook, or another generated function; verify the available parameters and exact generated source when possible. Check whether the SDK base hook already transmits a raw command frame, which could duplicate a mapped frame. Do not guess based on a snippet name or a successful build alone.

4. **Trace the complete device path.** Follow:

   ~~~text
   spoken phrase → SNA command ID → generated recognition callback → UART TX frame
   → STM32 UART RX/parser → command dispatch → mode/state gate → actuator driver → physical action
   ~~~

   For every stage, identify source evidence separately from hardware evidence. Confirm baud rate, frame length, which header/tail bytes are checked, the command byte position, and whether the callback sends one or multiple frames. Check state guards such as already-open/already-closed flags and any mode-dependent behavior.

5. **Map IDs to existing MCU commands.** Build a table from actual SNA IDs to existing STM32 command values. Reuse the existing protocol and drivers; do not invent new IDs or change hardware pin assignments. Unknown IDs must not trigger a device command. Keep the mapping small and localized to the intended voice callback.

6. **Verify at the right level.** Test mapping logic with runtime input/output tests when the toolchain is available. Include every configured command and unknown IDs. Run relevant STM32 C logic tests and the Keil build for STM32 source changes. State clearly that host/simulator tests do not validate generated callback placement, physical UART reception, electrical levels, supply stability, or motion.

7. **Separate wake timeout from reset symptoms.** Compare the active project timeout setting with the generated SDK/build configuration. A return to wake-word-only mode after a repeatable idle interval may be configured timeout. An immediate event tied to a load, repeated startup greeting, or a fresh boot pattern is evidence to investigate reset or supply/noise. Do not diagnose voltage instability from a beep alone; use a measured voltage at the module’s supply input during the event and record the load and measurement point.

8. **Keep hardware and flashing boundaries clear.** Preserve the user-confirmed board, wiring, and supply. Do not connect mains voltage or suggest unapproved hardware changes. The user performs physical flashing unless they explicitly authorize a different safe workflow. Report the exact source/configuration and generated BIN used for a test; do not equate local generation with successful flashing.

## Current project reference values

These values describe the current repository snapshot only. Re-read the files before applying them to any later build:

- The user has confirmed that the current new-version voice assistant and its generated/burned SNA firmware are usable. Treat this as the present known-good baseline, not proof that every command or hardware action is validated.
- The current SNA has UART0 configured at 9600 baud, header F4 06, and tail FB.
- cmd_007 / cmd_008 are the open-window / close-window commands. The voice mapping sends command bytes 0x05 / 0x06.
- The corresponding example frames are:

  ~~~text
  F4 06 05 FB  (open window)
  F4 06 06 FB  (close window)
  ~~~

- In the current STM32 working copy, USART1 initializes at 9600 baud. Its parser checks F4 at the start and FB at the end, reads the third byte as the command, and does not validate the second byte.
- HomeControl_Process handles 0x05 / 0x06 by setting curtain flags. The main loop checks CurtainFlag before calling MOTOR_Direction_Angle. If the software state already matches the requested state, that action may be skipped. There is no position sensor in this control path, so software state is only a target state.
- The current SNA timeout setting is 8 seconds; the SDK sample default EXIT_WAKEUP_TIME is 15000 ms. Verify the generated firmware’s effective timeout instead of assuming either value controls every build.

## Report format

For a diagnosis or change, report:

- Voice phrase and assigned ID → mapped MCU command.
- Relevant file and function at each layer.
- What is confirmed by source/test and what still needs a physical check.
- Backup location, changed files, and generated firmware identity when relevant.
- The smallest next user test that distinguishes recognition, UART, MCU dispatch, actuator, and power issues.

Never describe a TTS reply as proof of physical execution, a sent command as proof of motion, or an unmeasured power hypothesis as a confirmed voltage fault.
