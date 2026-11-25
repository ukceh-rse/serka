variable "deployment" {
  description = "test: a small instance with the 100-dataset bundle (dump-100.rdb); full: a 16 GB instance with the full bundle (dump-full.rdb)"
  type        = string

  validation {
    condition     = contains(["test", "full"], var.deployment)
    error_message = "deployment must be \"test\" or \"full\"."
  }
}

variable "connect_ip" {
  description = "CIDR block allowed to reach the UI, e.g. \"203.0.113.4/32\""
  type        = string
}

variable "vpc_id" {
  description = "Existing VPC ID where resources will be deployed"
  type        = string
}

variable "subnet_id" {
  description = "Existing subnet ID where the EC2 instance will be launched"
  type        = string
}

variable "git_ref" {
  description = "Branch, tag or commit of the serka repository to deploy"
  type        = string
  default     = "main"
}
