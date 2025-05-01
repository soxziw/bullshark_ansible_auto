#! you need to apply on server manually on correct NIC

# reorder receiving packages
## apply
sudo modprobe ifb
sudo ip link add ifb0 type ifb
sudo ip link set ifb0 up
sudo tc qdisc add dev $NIC handle ffff: ingress
sudo tc filter add dev $NIC parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev ifb0
sudo tc qdisc add dev ifb0 root handle 1: prio
sudo tc qdisc add dev ifb0 parent 1:1 handle 10: netem delay 10ms 2ms reorder 99% 0%
sudo tc filter add dev ifb0 protocol ip parent 1:0 prio 1 u32 \
    match ip dport 4000 0xffff \
    flowid 1:1

## delete 
sudo tc qdisc del dev ifb0 root
sudo tc qdisc del dev $NIC ingress
sudo ip link set ifb0 down
sudo ip link delete ifb0


# reorder sending packages
## apply
sudo tc qdisc add dev $NIC root handle 1: prio
sudo tc qdisc add dev $NIC parent 1:1 handle 10: netem delay 10ms 2ms reorder 99% 0%
sudo tc filter add dev $NIC protocol ip parent 1:0 prio 1 u32 \
    match ip dport 4000 0xffff \
    flowid 1:1

## delete
sudo tc qdisc del dev $NIC root


# centrol scheduler for local benchmark
## apply
sudo tc qdisc add dev lo root handle 1: prio
sudo tc qdisc add dev lo parent 1:1 handle 10: netem delay 10ms 2ms reorder 99% 0%

sudo tc filter add dev lo protocol ip parent 1:0 prio 1 u32 match ip dport 4000 0xffff flowid 1:1
sudo tc filter add dev lo protocol ip parent 1:0 prio 1 u32 match ip dport 4005 0xffff flowid 1:1
sudo tc filter add dev lo protocol ip parent 1:0 prio 1 u32 match ip dport 4010 0xffff flowid 1:1
sudo tc filter add dev lo protocol ip parent 1:0 prio 1 u32 match ip dport 4015 0xffff flowid 1:1

## delete
sudo tc qdisc del dev $NIC root