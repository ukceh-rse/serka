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

variable "ssh_key_name" {
  description = "Name of the existing AWS EC2 Key Pair to use for SSH"
  type        = string
}
