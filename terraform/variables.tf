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

variable "service_name" {
  description = "Name of the App Runner service."
  type        = string
  default     = "chess-opening-assistant"
}

variable "image_tag" {
  description = <<-EOT
    Image tag deployed when the service is first created. Every deploy after
    that is made by CI, and this value is then ignored -- see the lifecycle
    block in apprunner.tf. Set it in terraform.tfvars, which is not committed.
  EOT
  type        = string
}

variable "service_cpu" {
  description = "vCPU allocated to each instance."
  type        = string
  default     = "0.25 vCPU"
}

variable "service_memory" {
  description = "Memory allocated to each instance."
  type        = string
  default     = "0.5 GB"
}

variable "google_api_key_parameter" {
  description = "Parameter Store path holding the Gemini API key."
  type        = string
  default     = "/chess-opening-assistant/google-api-key"
}

variable "log_retention_days" {
  description = "How long App Runner's log groups keep events."
  type        = number
  default     = 14
}

variable "monthly_budget_usd" {
  description = "Monthly spend that triggers the budget notifications."
  type        = string
  default     = "10"
}

variable "budget_notification_email" {
  description = <<-EOT
    Address the budget alarm notifies. Deliberately has no default: this is a
    public repository, and an email address committed to one gets scraped. Set
    it in terraform.tfvars, which .gitignore excludes.
  EOT
  type        = string
}
