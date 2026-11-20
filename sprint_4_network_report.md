# Sprint 4 – CML 1-Router Network Verification Report

**Student:** Gale Wing (GW) · **Course:** CS 457 · **Date:** November 20, 2026
**DNS name:** `server.wing.edu` → `192.168.20.100`

---

## 1. Topology

![CML topology](images/topology.png)
<!-- TODO: screenshot of the CML canvas showing GW-R1, GW-Client1, GW-Client2, GW-Server, ext-conn-0 with link labels visible -->

| Node | Interface | Subnet | IP Address | How Assigned |
|---|---|---|---|---|
| GW-R1 | Gi0/0 | 192.168.255.0/24 | 192.168.255.227 | DHCP from External Connector (NAT outside) |
| GW-R1 | Gi0/1 | Subnet A – 192.168.10.0/24 | 192.168.10.1 | Static (gateway for Client 1) |
| GW-R1 | Gi0/2 | Subnet B – 192.168.11.0/24 | 192.168.11.1 | Static (gateway for Client 2) |
| GW-R1 | Gi0/3 | Subnet C – 192.168.20.0/24 | 192.168.20.1 | Static (gateway for Server) |
| GW-Client1 | eth0 | Subnet A | 192.168.10.2 | DHCP (`CLIENT1_POOL`) |
| GW-Client2 | eth0 | Subnet B | 192.168.11.2 | DHCP (`CLIENT2_POOL`) |
| GW-Server | eth0 | Subnet C | 192.168.20.100 | Static, default via 192.168.20.1 |

---

## 2. Router R1 Configuration (relevant sections of `show running-config`)

```
hostname R1
!
ip dhcp excluded-address 192.168.10.1
ip dhcp excluded-address 192.168.11.1
!
ip dhcp pool CLIENT1_POOL
 network 192.168.10.0 255.255.255.0
 default-router 192.168.10.1
 dns-server 192.168.10.1
!
ip dhcp pool CLIENT2_POOL
 network 192.168.11.0 255.255.255.0
 default-router 192.168.11.1
 dns-server 192.168.11.1
!
ip host server.wing.edu 192.168.20.100
!
interface GigabitEthernet0/0
 ip address dhcp
 ip nat outside
!
interface GigabitEthernet0/1
 ip address 192.168.10.1 255.255.255.0
 ip nat inside
!
interface GigabitEthernet0/2
 ip address 192.168.11.1 255.255.255.0
 ip nat inside
!
interface GigabitEthernet0/3
 ip address 192.168.20.1 255.255.255.0
 ip nat inside
!
ip dns server
ip nat inside source list 1 interface GigabitEthernet0/0 overload
!
access-list 1 permit 192.168.10.0 0.0.0.255
access-list 1 permit 192.168.11.0 0.0.0.255
access-list 1 permit 192.168.20.0 0.0.0.255
```
`ip routing` and `ip domain lookup` are IOS defaults, so they are active even though they don't appear in the running-config. The full config is in `sprint_4_topology.yaml`.

---

## 3. Router Verification Outputs

### 3.1 `show ip interface brief`
```
R1#sh ip int br
Interface                  IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0         192.168.255.227 YES DHCP   up                    up
GigabitEthernet0/1         192.168.10.1    YES manual up                    up
GigabitEthernet0/2         192.168.11.1    YES manual up                    up
GigabitEthernet0/3         192.168.20.1    YES manual up                    up
NVI0                       192.168.10.1    YES unset  up                    up
```
All routed interfaces are **up/up**. `NVI0` is the NAT Virtual Interface that IOS creates automatically when NAT is configured.

### 3.2 `show ip route`
```
R1#sh ip route
Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area
       N1 - OSPF NSSA external type 1, N2 - OSPF NSSA external type 2
       E1 - OSPF external type 1, E2 - OSPF external type 2
       i - IS-IS, su - IS-IS summary, L1 - IS-IS level-1, L2 - IS-IS level-2
       ia - IS-IS inter area, * - candidate default, U - per-user static route
       o - ODR, P - periodic downloaded static route, H - NHRP, l - LISP
       a - application route
       + - replicated route, % - next hop override, p - overrides from PfR

Gateway of last resort is 192.168.255.1 to network 0.0.0.0

S*    0.0.0.0/0 [254/0] via 192.168.255.1
      192.168.10.0/24 is variably subnetted, 2 subnets, 2 masks
C        192.168.10.0/24 is directly connected, GigabitEthernet0/1
L        192.168.10.1/32 is directly connected, GigabitEthernet0/1
      192.168.11.0/24 is variably subnetted, 2 subnets, 2 masks
C        192.168.11.0/24 is directly connected, GigabitEthernet0/2
L        192.168.11.1/32 is directly connected, GigabitEthernet0/2
      192.168.20.0/24 is variably subnetted, 2 subnets, 2 masks
C        192.168.20.0/24 is directly connected, GigabitEthernet0/3
L        192.168.20.1/32 is directly connected, GigabitEthernet0/3
      192.168.255.0/24 is variably subnetted, 2 subnets, 2 masks
C        192.168.255.0/24 is directly connected, GigabitEthernet0/0
L        192.168.255.227/32 is directly connected, GigabitEthernet0/0
```
All three LAN subnets appear as **Connected (C)** routes because they are attached directly to R1, so no static routes are needed between them. The default route (`S*`) was learned by DHCP from the External Connector and is used only for internet traffic.

### 3.3 `show ip dhcp binding`
```
R1#sh ip dhcp binding
Bindings from all pools not associated with VRF:
IP address          Client-ID/              Lease expiration        Type
                    Hardware address/
                    User name
192.168.10.2        0152.5400.1afd.4f       Nov 21 2026 09:17 PM    Automatic
192.168.11.2        0152.5400.b3f8.93       Nov 21 2026 09:18 PM    Automatic
```
Both clients hold active leases from their own pools. The hardware addresses match each client's `eth0` MAC: `52:54:00:1a:fd:4f` for Client 1 and `52:54:00:b3:f8:93` for Client 2.

---

## 4. Game Server (GW-Server) Verification

```
$ ip addr show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000
    link/ether 52:54:00:4f:1a:09 brd ff:ff:ff:ff:ff:ff
    inet 192.168.20.100/24 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::5054:ff:fe4f:1a09/64 scope link
       valid_lft forever preferred_lft forever
$ ip route
default via 192.168.20.1 dev eth0
192.168.20.0/24 dev eth0 scope link  src 192.168.20.100
```
Shows the static IP `192.168.20.100/24` and `default via 192.168.20.1`.

---

## 5. Client Verification

### 5.1 GW-Client1 (Subnet A)
```
$ ip addr show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000
    link/ether 52:54:00:1a:fd:4f brd ff:ff:ff:ff:ff:ff
    inet 192.168.10.2/24 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::5054:ff:fe1a:fd4f/64 scope link
       valid_lft forever preferred_lft forever
$ ip route
default via 192.168.10.1 dev eth0  metric 202
192.168.10.0/24 dev eth0 scope link  src 192.168.10.2
$ cat /etc/resolv.conf
nameserver 192.168.10.1
$ ping -c 4 192.168.20.100
PING 192.168.20.100 (192.168.20.100): 56 data bytes
64 bytes from 192.168.20.100: seq=0 ttl=42 time=2.958 ms
64 bytes from 192.168.20.100: seq=1 ttl=42 time=2.730 ms
64 bytes from 192.168.20.100: seq=2 ttl=42 time=3.374 ms
64 bytes from 192.168.20.100: seq=3 ttl=42 time=3.014 ms

--- 192.168.20.100 ping statistics ---
4 packets transmitted, 4 packets received, 0% packet loss
round-trip min/avg/max = 2.730/3.019/3.374 ms
$ nslookup -type=A server.wing.edu
Server:         192.168.10.1
Address:        192.168.10.1:53

Non-authoritative answer:
Name:   server.wing.edu
Address: 192.168.20.100
```

### 5.2 GW-Client2 (Subnet B)
```
$ ip addr show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000
    link/ether 52:54:00:b3:f8:93 brd ff:ff:ff:ff:ff:ff
    inet 192.168.11.2/24 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::5054:ff:feb3:f893/64 scope link
       valid_lft forever preferred_lft forever
$ ip route
default via 192.168.11.1 dev eth0  metric 202
192.168.11.0/24 dev eth0 scope link  src 192.168.11.2
$ cat /etc/resolv.conf
nameserver 192.168.11.1
$ ping -c 4 192.168.20.100
PING 192.168.20.100 (192.168.20.100): 56 data bytes
64 bytes from 192.168.20.100: seq=0 ttl=42 time=3.225 ms
64 bytes from 192.168.20.100: seq=1 ttl=42 time=3.219 ms
64 bytes from 192.168.20.100: seq=2 ttl=42 time=3.161 ms
64 bytes from 192.168.20.100: seq=3 ttl=42 time=3.333 ms

--- 192.168.20.100 ping statistics ---
4 packets transmitted, 4 packets received, 0% packet loss
round-trip min/avg/max = 3.161/3.234/3.333 ms
$ nslookup -type=A server.wing.edu
Server:         192.168.11.1
Address:        192.168.11.1:53

Non-authoritative answer:
Name:   server.wing.edu
Address: 192.168.20.100
```

Both clients received their IP, default gateway, and DNS server from R1 via DHCP, resolved `server.wing.edu` to `192.168.20.100`, and pinged the Game Server across the router with **0% packet loss**.

---

## 6. Wireshark DNS Capture (`sprint_4_dns_lookup.pcap`)

Captured on the link between **GW-Client1 eth0** and **GW-R1 Gi0/1** while running `nslookup -type=A server.wing.edu` on Client 1.

![Annotated Wireshark DNS exchange](images/wireshark_dns.png)
<!-- TODO: screenshot of Wireshark with packets 4 and 5 selected/highlighted, with arrows or boxes added -->

| Pkt | Source → Destination | Protocol | Description |
|---|---|---|---|
| 4 | 192.168.10.2:40477 → 192.168.10.1:**53** | DNS (UDP) | **Standard Query** (ID `0xa002`), type **A**, `server.wing.edu` |
| 5 | 192.168.10.1:**53** → 192.168.10.2:40477 | DNS (UDP) | **Standard Query Response** (ID `0xa002`), 1 answer: `server.wing.edu A` **192.168.20.100** |

**Annotations:**
- **Query (pkt 4):** Client 1 sends its query to R1 (`192.168.10.1`) because DHCP Option 6 set R1 as its DNS server. Destination port is UDP 53, and the flags are `0x0120` (standard query, recursion desired).
- **Response (pkt 5):** R1 answers from its local `ip host` table in about 14 ms. The flags are `0x8180` (response, no error), and the transaction ID matches the query, so the client knows this answer goes with its request.
- The other frames in the capture are background link traffic: CDP from R1, loopback keepalives, and ARP.

---

## 7. Summary

| Requirement | Result |
|---|---|
| Single router R1 with three routed subnets, interfaces up/up | ✅ |
| Separate DHCP pools with gateway exclusions, default-router, and dns-server | ✅ |
| Game Server static 192.168.20.100/24, default via 192.168.20.1 | ✅ |
| `server.wing.edu` resolves to 192.168.20.100 from both clients | ✅ |
| Zero-loss ping from both clients to the Game Server | ✅ |
| NAT/External Connector gives nodes internet access (`apk add git`) | ✅ |
