Title: P4编程实战
Date: 2018-05-07
Category: Tech
Tags: Network, P4lang, L3, L2
Slug: p4_helloworld
Author: subond
Summary: P4编程实战：利用p4编程强大的数据包处理能力，实现两个子网数据报的通信。

### 不同子网的通信

利用p4编程强大的数据包处理能力，实现两个子网数据报的通信。

子网1: 192.168.1.0/24
子网2: 192.168.2.0/24

### 编程思路

采用gre隧道的方式，将两个子网的数据包包裹在gre报文的内部，外部使用gre隧道进行通信。

### 核心代码

```go
# Ingress pipeline
control dataplane_route {
    apply(l3_or_l2) {
        l3_pkt {
            apply(host);
        }
    }
}

table l3_or_l2 {
    reads {
        inner_ethernet.dstAddr : exact;
        inner_ipv4 : valid;
    }

    actions {
        l3_pkt;
        l2_pkt;
    }
    default_action : l2_pkt();
    size : 1;
}

table host {
    reads {
        gretap.tunnelId : exact;
        inner_ipv4.dstAddr : exact;
    }

    actions {
        on_miss;
        forward_to;
    }
    default_action : on_miss();
    size : 10;
}
```

```
# Egress
table mac_info {
    reads {
        inner_ethernet.dstAddr : exact;
    }

    actions {
        forward_data;
        drop_act;
    }

    default_action : drop_act();
    size : 10;
}

table switch_pkt {
    reads {
        inner_ethernet.dstAddr : exact;
        inner_ipv4 : valid;
    }

    actions {
        is_switch;
        on_miss;
    }

    default_action : is_switch();
    size : 1;
}

control dataplane_switch {
    apply(switch_pkt) {
        is_switch {
            apply(mac_info);
        }
    }
}
```
