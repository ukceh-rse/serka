output "instance_id" {
  description = "ID of the EC2 instance deployed to."
  value       = aws_instance.app_server.id
}
