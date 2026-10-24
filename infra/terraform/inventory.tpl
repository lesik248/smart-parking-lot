[master]
master ansible_host=${nodes["master"].public_ip} private_ip=${nodes["master"].private_ip}

[workers]
worker-app ansible_host=${nodes["worker-app"].public_ip} private_ip=${nodes["worker-app"].private_ip} node_role=app
worker-db  ansible_host=${nodes["worker-db"].public_ip} private_ip=${nodes["worker-db"].private_ip} node_role=db

[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/k8s-lab
ansible_python_interpreter=/usr/bin/python3