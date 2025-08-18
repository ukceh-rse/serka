output "instance_url" {
  description = "HTTP URL for the EC2 instance."
  value       = "http://${aws_instance.app_server.public_ip}"
}
