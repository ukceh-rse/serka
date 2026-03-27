output "instance_id" {
  description = "ID of the EC2 instance deployed to."
  value       = aws_instance.app_server.id
}

output "alb_dns_name" {
  description = "DNS name of the ALB — use this as the CNAME target."
  value       = aws_lb.app.dns_name
}
