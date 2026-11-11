#!/bin/sh
set -eu

share=/mnt/cs-lab
mkdir -p "$share"
mount -t virtiofs cs-lab "$share"
finish() {
    status=$?
    printf '%s\n' "$status" > "$share/guest.exit"
    sync
    systemctl --no-block poweroff
}
trap finish EXIT
exec >> "$share/guest-bootstrap.log" 2>&1
export DEBIAN_FRONTEND=noninteractive

# This cloud disk belongs to the lab. The packages are fetched through guest NAT.
sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources
apt-get -o Acquire::Retries=2 -o Acquire::https::Timeout=30 update
apt-get -o Acquire::Retries=2 -o Acquire::https::Timeout=30 install -y --no-install-recommends \
    openjdk-17-jre-headless iproute2 iptables socat

# Provisioning uses NAT. The three test namespaces are connected only by veth pairs.
cp -r "$share/bundle" /opt/cs-lab
python3 "$share/guest.py" /opt/cs-lab "$share/results"
