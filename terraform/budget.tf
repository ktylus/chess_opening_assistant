# The backstop for everything else.
#
# A public endpoint that pays a model provider per request can, in principle,
# be made expensive by anyone who finds it. The rate limiter in
# backend/app/rate_limit.py slows that down and a quota cap on the API key at
# Google's end bounds it, but neither tells you it is happening. This does.

resource "aws_budgets_budget" "monthly" {
  name         = "${var.service_name}-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Actual spend, once most of the month's budget is gone.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_notification_email]
  }

  # Forecast, which is the one that catches a runaway early: spend does not
  # have to have happened yet for the trend to be alarming.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_notification_email]
  }
}
