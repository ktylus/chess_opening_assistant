# The Gemini API key.
#
# Terraform owns the parameter but deliberately not its value. Anything passed
# through a Terraform variable is written to state in plaintext, so the real key
# is put in out of band and the value here is ignored from then on:
#
#   aws ssm put-parameter --name /chess-opening-assistant/google-api-key \
#     --type SecureString --value "<key>" --overwrite
#
# App Runner reads it at instance start via runtime_environment_secrets, so the
# key is never in the image, the repository, or the service configuration.

resource "aws_ssm_parameter" "google_api_key" {
  name        = var.google_api_key_parameter
  description = "Gemini API key used by the agent at runtime."
  type        = "SecureString"
  value       = "placeholder -- replace with aws ssm put-parameter --overwrite"

  lifecycle {
    ignore_changes = [value]
  }
}
