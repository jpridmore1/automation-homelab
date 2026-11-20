# OT Security Assessment: Simulated Modbus PLC

This lab simulates a small water-tank process controlled by a PLC over **Modbus TCP**, then attacks it, segments it, and monitors it. Everything here was run against my own simulated device in rootless Podman on Fedora; all output below is from actual test runs.

> Only test equipment you own or are authorized to test.

## Lab architecture

```
        IT zone (it-net, 10.89.1.0/24)          OT zone (ot-net, 10.89.0.0/24)
     ┌──────────────────────────────┐       ┌──────────────────────────────────┐
     │  "attacker" / IT workstation │       │  HMI poller        plc-sim       │
     │                              │   X   │  (Modbus reads) ──► (Modbus 502) │
     └──────────────────────────────┘       │                      ▲           │
                    │                        │   tshark sensor ─────┘           │
                    │                        └──────────────────────────────────┘
                    └── host (Fedora) ── PLC port published on 127.0.0.1:5020 only
```

| Component | Role |
|---|---|
| `plc/plc_sim.py` | Simulated PLC: 1 s scan cycle, tank level with pump hysteresis control (on at 20%, off at 80%) |
| `plc/read_plc.py` | Minimal HMI: polls coils and holding registers every 2 s |
| `ot-net` / `it-net` | Podman bridge networks representing the OT and IT zones |

**Register map**

| Address | Type | Meaning |
|---|---|---|
| Coil 0 | Coil | Pump running |
| Coil 1 | Coil | Auto mode (PLC logic in control) |
| HR 0 | Holding register | Tank level (0–100 %) |
| HR 1 | Holding register | Temperature (tenths of °C) |
| HR 2 / HR 3 | Holding register | High / low setpoints |

## Finding 1: Modbus TCP has no authentication

Any host that can reach TCP/502 can write to the PLC. From an unauthorized container on the OT network, two `Write Single Coil` requests disabled auto mode and forced the pump on.

PLC log during the attack:

```
plc level= 79%  pump=OFF  auto=True     <- normal: stopped at high setpoint
plc level= 81%  pump=ON   auto=False    <- rogue writes land
plc level= 99%  pump=ON   auto=False
plc level=100%  pump=ON   auto=False    <- tank overflowing, logic bypassed
```

The HMI showed the same values but raised **no alarm** and gave no indication of who made the change.

**Impact:** loss of control and overflow of the simulated tank. In a real process this is a safety event.

## Finding 2: Separate subnets were not segmentation

The two zones used different subnets (`10.89.0.0/24` and `10.89.1.0/24`), and the PLC's hostname did not resolve from the IT zone, which *looked* like isolation. But connecting to the PLC by IP from the IT zone succeeded: the host routed between the bridge networks.

**Fix:** recreate both networks with Podman's `isolate=true` option, which adds firewall rules dropping inter-network traffic.

```bash
podman network create --opt isolate=true ot-net
podman network create --opt isolate=true it-net
```

## Finding 3: Published host port bypassed the zone boundary

The PLC port was published on all host interfaces (`-p 5020:502`). From the IT zone, `host.containers.internal:5020` reached the PLC through the host, bypassing segmentation entirely.

**Fix:** bind the published port to loopback only.

```bash
podman run -d --name plc-sim --network ot-net -p 127.0.0.1:5020:502 localhost/plc-sim
```

## Verification after hardening

| # | Attack path | Result | Failure signature | Control |
|---|---|---|---|---|
| 1 | IT zone → PLC by IP | **Blocked** | `timed out` (packets dropped) | Network isolation |
| 2 | IT zone → host port → PLC | **Blocked** | `Connection refused` | Loopback-only port binding |
| 3 | Device attached to **both** zones | **Succeeded** | — | None: the conduit bypasses segmentation |

The two failure signatures are themselves informative: a *timeout* means a firewall silently dropped the traffic; a *refusal* means the host actively reported nothing listening.

An `nmap -sT -p 502` sweep of `10.89.0.0/24` confirmed the result: from the OT zone the PLC showed `502/tcp open`; from the IT zone it showed `filtered`.

**Test 3 is the key lesson:** segmentation is only as strong as the devices that bridge zones (historians, jump hosts, engineering laptops). These conduits must be identified, minimized, hardened, and monitored.

## Detection: passive monitoring at the PLC

A `tshark` sensor attached to the PLC's network namespace (equivalent to a SPAN port) captured all Modbus traffic.

**Baseline:** one client (the HMI), function codes 1 (Read Coils) and 3 (Read Holding Registers) only, at a fixed 2-second interval, with monotonically increasing transaction IDs.

**Anomaly:**

```
2114 698.070  10.89.0.17 → 10.89.0.3  Query:    Trans: 1; Unit: 1, Func: 5: Write Single Coil
2116 698.070  10.89.0.3 → 10.89.0.17  Response: Trans: 1; Unit: 1, Func: 5: Write Single Coil
```

Three indicators break the baseline at once:

- **New source IP** that had never communicated with the PLC
- **New function code** (5, a write) where the baseline was read-only
- **New session** (transaction ID 1 mid-stream)

Two observations:

- **Blocked attempts (tests 1 and 2) left no trace at the PLC.** The traffic was dropped before arriving, so detecting attempted intrusions requires monitoring and logging at the zone boundary as well.
- **The legitimate restore command also triggered the same indicators.** A write-based alert cannot distinguish authorized from unauthorized changes on its own; an allowlist of approved engineering stations and alert triage are required.

## Control mapping

| Control in this lab | IEC 62443-3-3 | NIST CSF 2.0 |
|---|---|---|
| Separate OT / IT networks with `isolate=true` | SR 5.1 Network segmentation | PR.IR-01 |
| Loopback-only port binding at the host | SR 5.2 Zone boundary protection | PR.IR-01 |
| Rootless containers, Podman's dropped capabilities (`NET_RAW`), capabilities added only for the sensor | SR 2.1 Authorization enforcement (least privilege) | PR.AA-05 |
| Passive Modbus monitoring with a learned baseline | SR 6.2 Continuous monitoring | DE.CM-01 |
| **Gap:** Modbus has no device or user authentication | SR 1.2 (not met by protocol) | PR.AA-03 |

NIST SP 800-82 Rev. 3 (*Guide to OT Security*) recommends the same defense-in-depth approach: segment OT from IT, tightly control and monitor conduits, and monitor OT networks for anomalous behavior.

## Next improvements

- [ ] Deploy the PLC, networks, and hardening with Ansible so the secure configuration is the default
- [ ] HMI high-level alarm (alert when level exceeds the high setpoint)
- [ ] Automated detection: alert on any Modbus write from a source not on an allowlist
- [ ] Boundary logging so blocked attempts are visible
- [ ] Modbus-aware filtering at the conduit (allow reads, deny writes from the IT side)
