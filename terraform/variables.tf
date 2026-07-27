variable "aws_region" {
  description = "Region hosting every resource in this configuration."
  type        = string
  default     = "eu-central-1"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository holding the application image."
  type        = string
  default     = "chess-opening-assistant"
}

variable "github_repository" {
  description = "owner/name of the repository whose workflows may push images."
  type        = string
  default     = "ktylus/chess_opening_assistant"
}

variable "github_branch" {
  description = "The only branch whose workflow runs may push images."
  type        = string
  default     = "main"
}

variable "image_retention_count" {
  description = "Number of tagged images kept before the oldest are expired."
  type        = number
  default     = 10
}
