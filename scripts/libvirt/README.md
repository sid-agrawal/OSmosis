Based on instructions from here:

https://docs.beamnetworks.dev/en/kvm/create-vm-full

https://www.surlyjake.com/blog/2020/10/09/ubuntu-cloud-images-in-libvirt-and-virt-manager/


```bash
sudo virt-install \
  --name foo-tester \
  --memory 4096 \
  --vcpus 4 \
  --os-type linux \
  --os-variant ubuntu20.04 \
  --network bridge=virbr0 \
  --nographics --disk size=10,backing_store=$PWD"/focal-server-cloudimg-amd64.img",bus=virtio \
  --cloud-init user-data=$PWD"/user-data",meta-data=${PWD}"/meta-data"
```
