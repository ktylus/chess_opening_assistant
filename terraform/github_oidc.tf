# How GitHub Actions authenticates to AWS without a stored key.
#
# A workflow run is issued a short-lived, signed token by GitHub that states
# which repository, branch and event produced it. Registering GitHub as an
# identity provider lets AWS verify that signature; the role's trust policy
# below then decides which of those tokens it is willing to accept. The
# workflow exchanges the token for credentials that expire within the hour, so
# there is no AWS_SECRET_ACCESS_KEY stored in GitHub to leak or to rotate.

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  # The audience configure-aws-credentials asks GitHub to stamp on the token.
  # Re-checked in the trust policy, which is what stops a token minted for some
  # other consumer from being replayed against this role.
  client_id_list = ["sts.amazonaws.com"]

  # thumbprint_list is deliberately absent. IAM validates this endpoint against
  # its own library of trusted root CAs and ignores any thumbprint configured
  # for it, so pinning one buys nothing and adds a certificate rotation to
  # forget about. Requires provider >= 6.0, where the argument became optional.
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # The subject claim is the entire security boundary, and it is matched
    # exactly against one repository on one branch. A run on another branch, on
    # a pull request, or in a fork produces a different `sub` and is refused.
    #
    # StringLike with a "repo:owner/name:*" wildcard is the common shortcut and
    # the common breach: it accepts pull request runs, and a pull request can
    # be opened by anyone.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/${var.github_branch}"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "github-actions-ecr-push"
  description        = "Assumed by GitHub Actions to push images to ${var.ecr_repository_name}."
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}

data "aws_iam_policy_document" "ecr_push" {
  # The one ECR action that takes no resource: it hands back a registry-wide
  # login token, so "*" is as narrow as this statement can be written.
  statement {
    sid       = "AuthenticateToRegistry"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Upload, and only into this one repository. No delete, no repository policy
  # changes, and nothing at all outside ECR -- which is what makes it safe for
  # this role to be assumable by an automated system.
  #
  # BatchGetImage is a read, and is required despite this being a push-only
  # role: the registry protocol has the client HEAD the manifest before
  # uploading it, and ECR authorises manifest reads with that action. Without
  # it the push fails at the very last step with a bare 403.
  statement {
    sid    = "PushImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app.arn]
  }
}

resource "aws_iam_role_policy" "ecr_push" {
  name   = "ecr-push"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.ecr_push.json
}

# Deploying is a second, separate grant: point one named service at one image
# and watch it settle. Notably absent are CreateService and DeleteService --
# the service's existence and its shape stay with Terraform, and CI may only
# change which image it runs.
data "aws_iam_policy_document" "apprunner_deploy" {
  statement {
    sid    = "UpdateRunningImage"
    effect = "Allow"
    actions = [
      "apprunner:DescribeService",
      "apprunner:UpdateService",
    ]
    resources = [aws_apprunner_service.app.arn]
  }

  # UpdateService restates the source configuration, which names the role App
  # Runner pulls the image with -- and handing a role to a service is itself a
  # privileged act, so it is granted for exactly one role and no other.
  #
  # An iam:PassedToService condition would be the belt-and-braces version, but
  # App Runner does not report the value its own documentation implies for this
  # call and the condition simply never matches. Little is lost: the role named
  # here can only be assumed by App Runner's build principal in the first
  # place, so passing it elsewhere achieves nothing.
  statement {
    sid       = "PassImagePullRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.apprunner_access.arn]
  }
}

resource "aws_iam_role_policy" "apprunner_deploy" {
  name   = "apprunner-deploy"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.apprunner_deploy.json
}
