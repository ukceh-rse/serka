variable "instance_name" {
  description = "Value of the EC2 instance's Name tag."
  type        = string
  default     = "serka"
}

variable "instance_type" {
  description = "The EC2 instance's type."
  type        = string
  default     = "t3.micro"
}

variable "connect_ip" {
  description = "IP address to allow connections from"
  type = string
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID where resources will be deployed"
}

variable "subnet_id" {
  type        = string
  description = "Existing Subnet ID where the EC2 instance will be launched"
}
