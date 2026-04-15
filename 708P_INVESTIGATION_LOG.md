# JBL 708P Investigation Log

Last updated: 2026-04-12

## Summary

The speaker at `192.168.2.145` exposes:

- FTP on `21/TCP`
- a live WebSocket control API on `19273/TCP`
- no useful response to our earlier HiQnet discovery/control attempts on `3804/TCP+UDP`

The FTP service appears to be a standard QNX Neutrino FTP daemon:

- Banner: `220 192.168.2.145 FTP server (QNXNTO-ftpd 20081216) ready.`
- `SYST`: `215 UNIX Type: L8 Version: QNXNTO-ftpd 20081216`
- `STAT` before login reports `Waiting for user name`
- `HELP`, `FEAT`, `SYST`, `STAT`, and `OPTS MLST ...` all work without authentication

The key breakthrough is the WebSocket API on `19273/TCP`. It exposes a path-based object tree and accepts read/write commands such as `lc`, `get`, and `set`, which makes it a far more practical control path than the original HiQnet `3804` probing route.

## Direct Findings

### Network behavior

- Host machine: `192.168.2.132`
- Target speaker: `192.168.2.145`
- MAC address observed by ARP: `00-0A-40-20-05-06`
- `192.168.2.145` responds to ping
- TCP `21` is open
- TCP `19273` is open and accepts a standard WebSocket upgrade
- TCP `3804` did not accept our control attempts in prior probing
- UDP broadcast and unicast HiQnet discovery produced no reply from the speaker

### WebSocket API behavior

Observed directly against `192.168.2.145:19273`:

- handshake:
  - `HTTP/1.1 101 WebSocket Protocol Handshake`
- confirmed device identity:
  - `\\this\Node\AT\Class_Name` -> `LSR708`
  - `\\this\Node\AT\Instance_Name` -> `LSR708`
  - `\\this\Node\AT\Software_Version` -> `1.0.6.0`
- confirmed read commands:
  - `lc "\\this"`
  - `lc "\\this\Node"`
  - `get "\\this\Node\SpeakerGain\SV\Channel_1_Gain"`
- confirmed write grammar:
  - `set "\\this\Node\LSR7Hardware\SV\LCDLight" "On"`
  - `set "\\this\Node\SpeakerGain\SV\Channel_1_Gain\%" 100`

Confirmed branches under `\\this\Node` include:

- `DSPInputs`
- `DSPOutputs`
- `InputMixer`
- `UserEQ`
- `BassMgmtXover`
- `SpeakerEQ_Lo`
- `SpeakerEQ_Hi`
- `RoomEQ`
- `RoomDelay`
- `FrameDelay`
- `SpeakerGain`
- `SpeakerTrim`
- `SystemHP`
- `SideChainLP_Hi`
- `SideChainLP_Lo`
- `SideChainEQ_Lo`
- `SideChainEQ_Hi`
- `Limiter_Lo`
- `Limiter_Hi`
- `CompLowpass_Lo`
- `CompHighpass_Hi`
- `CompDelay_Hi`
- `CompGain_Hi`
- `AnalogInputMeter`
- `AES1InputMeter`
- `AES2InputMeter`
- `OutputHiMeter`
- `OutputLoMeter`
- `ChannelInputMeter`
- `LSR7Hardware`
- `SV`
- `AT`
- `DA`

Representative live values:

- `\\this\Node\SpeakerGain\SV\Channel_1_Gain` -> `0.0dB`
- `\\this\Node\SpeakerGain\SV\Channel_1_Mute` -> `Off`
- `\\this\Node\RoomEQ\SV\Enable` -> `Off`
- `\\this\Node\RoomDelay\SV\Out_1_Delay` -> `0ms/0ft/0m`
- `\\this\Node\LSR7Hardware\SV\LCDLight` -> `On`

### FTP unauthenticated behavior

Observed with `curl.exe` and `ftp.exe` using read-only commands only:

- Banner:
  - `220 192.168.2.145 FTP server (QNXNTO-ftpd 20081216) ready.`
- Anonymous flow:
  - `USER anonymous` -> `331 Guest login ok, type your name as password.`
  - `PASS ftp@example.com` -> `550 Can't set guest privileges.`
- `HELP` output shows a broad command set, including:
  - `USER`, `PASS`, `PORT`, `PASV`, `EPSV`, `RETR`, `STOR`, `LIST`, `NLST`, `MLSD`, `SITE`, `SYST`, `STAT`, `MDTM`, `SIZE`
- `FEAT` output:
  - `MDTM`
  - `MLST Type*;Size*;Modify*;Perm*;Unique*;`
  - `REST STREAM`
  - `SIZE`
  - `TVFS`
- `OPTS MLST Type;Size;Modify;Perm;Unique;` -> `200 MLST OPTS Type;Size;Modify;Perm;Unique;`

### Interpretation

- The daemon is not a fake or application-specific FTP shim; it behaves like a fairly standard UNIX/QNX FTP server.
- The anonymous response is informative:
  - the server recognizes guest login semantics
  - guest access is not successfully established
  - likely causes are disabled/broken guest privilege setup, missing guest home/chroot, or intentional anonymous denial
- Because unauthenticated introspection works, this service is likely a general-purpose maintenance surface inherited from the device OS / platform rather than a tiny custom firmware-only endpoint.

## Official Source Notes

### JBL / Harman product behavior

- JBL 708P product page says the rear RJ-45 is for `HARMAN HiQnet connectivity`.
- The same page also says the HiQnet port `enables feature updates as they become available`.
- The 7P owner’s manual documents front-panel `Network Configuration` settings including IP, MAC, subnet, gateway, and DHCP/manual IP.

Sources:

- [JBL 708P product page](https://jblpro.com/en-US/products/708p.html)
- [7P Series Owner's Manual](https://jblpro.com/en-US/site_elements/7p-series-owner-s-manual)

### HiQnet discovery / addressing constraints

- Harman says all HiQnet devices must have a unique node address.
- Harman documents that a HiQnet device with address `0` will not be recognized by HiQnet software.
- Harman troubleshooting also notes that device discovery can fail because of bad network settings, gateway issues, VLAN issues, or other device/network configuration problems.

Sources:

- [Connecting to a HiQnet Network](https://help.harmanpro.com/en_US/hiqnet-audio-architect/audio-architect-connecting-to-a-hiqnet-network)
- [HiQnet Device not Discovered in Audio Architect or Netsetter](https://help.harmanpro.com/hiqnet-device-not-discovered-in-audio-architect-or-netsetter)
- [Troubleshooting HiQnet Device Discovery Using Audio Architect](https://help.harmanpro.com/en_US/troubleshooting-hiqnet-device-discovery-using-audio-architect)

### Harman use of FTP on HiQnet-family devices

- Harman officially documents `21/TCP` as FTP used for:
  - loading configuration
  - loading firmware
  - transferring event logs
- This specific documentation is for some Soundweb / Contrio devices, not explicitly the 708P, but it shows that FTP is a normal maintenance path within the Harman HiQnet ecosystem.

Source:

- [HARMAN HiQnet Communication On A Routed Network](https://help.harmanpro.com/en_US/hiqnet-communication-on-a-routed-network)

### Third-party control expectations

- Harman’s own third-party documentation says the publicly available HiQnet methods are limited and not every device is documented in detail.
- Harman also says HiQnet is not a public API in the broader support sense.

Sources:

- [HiQnet Third Party Programmer Documentation](https://help.harmanpro.com/en_US/hiqnet-third-party-programmer-documentation)
- [Third-Party Control of Crown Amplifiers](https://help.harmanpro.com/third-party-control-of-crown-amplifiers)

## Ranked Hypotheses

1. The powered speaker's primary usable network control path is the WebSocket API on `19273/TCP`.
2. The FTP service is a real maintenance/update surface, but not anonymously accessible.
3. The older HiQnet `3804` path is not the practical control surface for this unit, at least in its current firmware/configuration state.
4. The device likely shares protocol and platform concepts with Harman/Intonato tooling, but uses its own LSR7-specific object tree.

## What We Did Not Do

- No password guessing beyond anonymous guest semantics
- No file upload, delete, rename, or directory creation
- No firmware push or reset
- No use of mutating FTP commands such as `STOR`, `DELE`, `RNFR`, `RNTO`, `MKD`, `RMD`

## Recommended Next Steps

### Safe next steps

- Inspect the speaker front panel for:
  - DHCP/manual IP
  - current network settings
  - any HiQnet address / device ID / node ID
  - feature update / utility / lock state
- Capture traffic while changing a network setting or rebooting the speaker.
- Look for official JBL/Harman firmware packages or update notes for the 708P or 7P line.

### Higher-risk next step

- Attempt a small, curated credential set against FTP, stopping on first success and keeping post-login activity read-only.
- This should be done only if explicitly desired, because even a bounded login campaign is still an authentication attack on the device.
