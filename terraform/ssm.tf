# The credentials the running container needs.
#
# Terraform owns these parameters but deliberately not their values. Anything
# passed through a Terraform variable is written to state in plaintext, so the
# real secrets are put in out of band and the values here are ignored from then
# on:
#
#   aws ssm put-parameter --name /chess-opening-assistant/google-api-key \
#     --type SecureString --value "<key>" --overwrite
#
# App Runner reads them at instance start via runtime_environment_secrets, so
# nothing is in the image, the repository, or the service configuration -- only
# the parameter ARNs are. That resolution happens once per instance, which means
# a value replaced in SSM does not reach the application until the next
# deployment.

resource "aws_ssm_parameter" "google_api_key" {
  name        = var.google_api_key_parameter
  description = "Gemini API key used by the agent at runtime."
  type        = "SecureString"
  value       = "placeholder -- replace with aws ssm put-parameter --overwrite"

  lifecycle {
    ignore_changes = [value]
  }
}

# The masters explorer answers unauthenticated requests with 401, so this is
# required despite backend/agent/tools.py treating the token as optional and
# simply omitting the Authorization header when it is unset.
resource "aws_ssm_parameter" "lichess_api_key" {
  name        = var.lichess_api_key_parameter
  description = "Lichess API token used for the masters opening explorer."
  type        = "SecureString"
  value       = "placeholder -- replace with aws ssm put-parameter --overwrite"

  lifecycle {
    ignore_changes = [value]
  }
}
