output "instance_id" {
  description = "ID of the EC2 instance deployed to."
  value       = aws_instance.app_server.id
}

output "instance_url" {
  description = "URL of the Serka UI (public IP, if the subnet assigns one, otherwise private)."
  value       = "http://${coalesce(aws_instance.app_server.public_ip, aws_instance.app_server.private_ip)}:8080"
}
