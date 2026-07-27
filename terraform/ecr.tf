# The registry.
#
# One repository, one image, tagged with the short commit SHA -- the same value
# baked in as the GIT_SHA build arg and reported at runtime by
# backend/observability/provenance.py. A log line therefore names an image, and
# the image names a commit.

resource "aws_ecr_repository" "app" {
  name = var.ecr_repository_name

  # A tag is a commit, and a commit does not change its contents. Immutability
  # makes that a rule the registry enforces rather than a convention CI is
  # trusted to keep, so an image pulled twice is byte-identical twice.
  #
  # The cost: re-running a workflow that already pushed fails at the push step,
  # because the tag exists. That is the correct outcome -- the image is already
  # there -- but it looks like a failure in the Actions UI.
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  # ECR bills per GB stored. Without expiry, every commit ever pushed is kept
  # forever, and the plan's "~$0 for ECR" line stops being true within a year.
  #
  # Rules are evaluated in priority order and an image is expired by the first
  # rule that selects it.
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged layers left behind by newer builds"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = { type = "expire" }
      },
    ]
  })
}
