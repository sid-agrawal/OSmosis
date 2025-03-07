Based on instructions from here:

https://docs.beamnetworks.dev/en/kvm/create-vm-full

https://www.surlyjake.com/blog/2020/10/09/ubuntu-cloud-images-in-libvirt-and-virt-manager/


Get Image
```bash
wget https://cloud-images.ubuntu.com/daily/server/daily/server/focal/current/focal-server-cloudimg-amd64.img
```

Change root and ubuntu password
```bash
export IMAGE_NAME=focal-server-cloudimg-amd64.img
virt-customize -a $IMAGE_NAME  --root-password password:password
virt-customize -a $IMAGE_NAME  --password ubuntu:password:password
```

This is the username password pairs.

root password 
ubuntu password

```bash
sudo virt-install \
  --name foo-tester \
  --memory 4096 \
  --vcpus 4 \
  --os-variant ubuntu20.04 \
  --network bridge=virbr0 \
  --nographics --disk size=10,backing_store=$PWD"/focal-server-cloudimg-amd64.img",bus=virtio \
  --cloud-init user-data=$PWD"/user-data",meta-data=${PWD}"/meta-data"
```
