# Log retention.
#
# App Runner writes to two groups: `service`, which carries deployment and
# health-check activity, and `application`, which carries the container's
# stdout -- the structured events from backend/observability. Both default to
# retaining forever, which is the entire reason they are managed here.
#
# App Runner creates these groups itself, and their names contain a service id
# that does not exist until it has. Terraform therefore cannot create them, only
# adopt them, and the first apply is expected to fail here with
# ResourceAlreadyExistsException *after* the service itself is created. Recover
# by importing whichever groups already exist and applying again:
#
#   terraform import aws_cloudwatch_log_group.service \
#     "/aws/apprunner/<service_name>/<service_id>/service"
#
# `terraform output` prints both parts of that name. The `application` group is
# only created once the container logs for the first time, so it may not exist
# yet -- if the import says no such group, let apply create it instead.

resource "aws_cloudwatch_log_group" "service" {
  name              = "/aws/apprunner/${aws_apprunner_service.app.service_name}/${aws_apprunner_service.app.service_id}/service"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/apprunner/${aws_apprunner_service.app.service_name}/${aws_apprunner_service.app.service_id}/application"
  retention_in_days = var.log_retention_days
}
