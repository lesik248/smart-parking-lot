variable "project" {
  type    = string
  default = "k8s-lab"
}

variable "region" {
  type    = string
  default = "eu-north-1"
}

variable "my_ip" {
  description = "Your public IP"
  type        = string
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/k8s-lab.pub"
}

variable "instance_type" {
  type    = string
  default = "t3.small" 
}