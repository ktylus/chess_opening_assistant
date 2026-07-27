# The service. One container serving the API and the built frontend, reachable
# on an HTTPS URL App Runner provides -- no load balancer, no certificate, no
# domain. See notes/deployment_plan.md for why this is not ECS behind an ALB.

# ---------------------------------------------------------------------------
# Roles.
#
# App Runner uses two, for two different principals, and conflating them is the
# usual reason a service will not start. The access role belongs to the build
# side and is used to pull the image before anything runs. The instance role
# belongs to the running container and is what the application's own AWS calls
# are made as -- here, only reading the API key.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "apprunner_access_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_access" {
  name               = "${var.service_name}-apprunner-access"
  description        = "Lets App Runner pull the application image from ECR."
  assume_role_policy = data.aws_iam_policy_document.apprunner_access_assume.json
}

resource "aws_iam_role_policy_attachment" "apprunner_access" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

data "aws_iam_policy_document" "apprunner_instance_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_instance" {
  name               = "${var.service_name}-apprunner-instance"
  description        = "Identity the running container makes AWS calls as."
  assume_role_policy = data.aws_iam_policy_document.apprunner_instance_assume.json
}

# The parameter is a SecureString, so reading it is two permissions, not one:
# fetching the ciphertext from SSM and decrypting it with the AWS-managed key
# that SSM used. Granting only the first fails at deploy time with an error
# that names neither KMS nor the key.
data "aws_kms_alias" "ssm" {
  name = "alias/aws/ssm"
}

data "aws_iam_policy_document" "read_api_key" {
  statement {
    effect    = "Allow"
    actions   = ["ssm:GetParameters"]
    resources = [aws_ssm_parameter.google_api_key.arn]
  }

  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [data.aws_kms_alias.ssm.target_key_arn]
  }
}

resource "aws_iam_role_policy" "read_api_key" {
  name   = "read-api-key"
  role   = aws_iam_role.apprunner_instance.id
  policy = data.aws_iam_policy_document.read_api_key.json
}

# ---------------------------------------------------------------------------
# Scaling.
#
# Pinned to exactly one instance. That is a cost control first -- nothing can
# scale into a surprise bill -- but it is also what makes the in-process state
# elsewhere in the application correct: the rate limiter's counters and the
# Stockfish cache are per-process, and both assume there is only ever one.
# ---------------------------------------------------------------------------

resource "aws_apprunner_auto_scaling_configuration_version" "app" {
  auto_scaling_configuration_name = var.service_name

  min_size        = 1
  max_size        = 1
  max_concurrency = 100
}

# ---------------------------------------------------------------------------
# The service.
# ---------------------------------------------------------------------------

resource "aws_apprunner_service" "app" {
  service_name = var.service_name

  source_configuration {
    # Deploys are explicit. Auto-deployment watches a fixed tag for changes,
    # which needs a moving tag like `latest`; the repository here is immutable
    # and tagged by commit, so CI names the exact image to run instead. The
    # cost is a deploy step in the workflow; the gain is that rolling back is
    # redeploying a tag that still means what it meant when it was built.
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        # Resolved by App Runner at instance start using the instance role, so
        # the value appears in the container's environment and nowhere else.
        runtime_environment_secrets = {
          GOOGLE_API_KEY = aws_ssm_parameter.google_api_key.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.service_cpu
    memory            = var.service_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  # /health touches no external service, so a failure here means the process is
  # genuinely unhealthy rather than that Gemini is having a bad day.
  #
  # The thresholds are loose on purpose: backend/app/app.py builds the
  # retrieval client at import, so the first probe can arrive before the
  # application is ready to answer it.
  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.app.arn

  lifecycle {
    # CI moves the service to a new tag on every push to main, so after
    # creation the running image is not something this configuration knows or
    # should try to correct. Without this, the next apply would quietly roll
    # production back to var.image_tag.
    ignore_changes = [
      source_configuration[0].image_repository[0].image_identifier,
    ]
  }
}
