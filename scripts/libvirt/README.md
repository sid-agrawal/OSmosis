Based on instructions from here:

https://docs.beamnetworks.dev/en/kvm/create-vm-full


```bash
sudo virt-install \
  --name foo-tester \
  --memory 4096 \
  --vcpus 4 \
  --os-type linux \
  --os-variant ubuntu20.04 \
  --network bridge=virbr0 \
  --nographics --disk size=10,backing_store=$PWD"/ubuntu-24.04-server-cloudimg-amd64.img",bus=virtio \
  --cloud-init user-data=$PWD"/user-data",meta-data=${PWD}"/meta-data"
```
