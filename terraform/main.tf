# Applied from a workstation, never from CI:
#
#   $env:AWS_PROFILE = "<sso profile>"
#   terraform init
#   terraform apply
#
# Infrastructure and application therefore move on separate tracks. A commit
# ships by CI pushing a new image tag; infrastructure changes only when someone
# runs apply. That separation is why the role created here can push images and
# do nothing else: a compromised workflow cannot reshape the account.

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # 6.0 made thumbprint_list optional on the OIDC provider; see
      # github_oidc.tf. The exact version in use is pinned by
      # .terraform.lock.hcl, which is committed -- this only sets the floor.
      version = ">= 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Applied to everything that supports tags, so the whole stack can be found,
  # or cost-attributed, without knowing what it was named.
  default_tags {
    tags = {
      Project   = "chess-opening-assistant"
      ManagedBy = "terraform"
    }
  }
}
