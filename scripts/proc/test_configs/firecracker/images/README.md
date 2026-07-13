# Firecracker guest images

The scenario boots two real microVMs, so it needs a kernel and a rootfs. Without them the
setup script prints `SKIP=`. Fetch them from the Firecracker CI bucket:

```sh
B=https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64
curl -fsSL -o vmlinux      "$B/vmlinux-5.10.223"
curl -fsSL -o rootfs.ext4  "$B/ubuntu-22.04.ext4"
```

They are deliberately not committed (~340 MB).
