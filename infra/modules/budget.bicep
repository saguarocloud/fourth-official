// Monthly subscription budget with email alerts on actual spend.

targetScope = 'subscription'

param name string

@minValue(1)
param amount int

@description('First day of a month (yyyy-MM-01). Fixed, because a budget start date cannot move later.')
param startDate string

param contactEmails string[]

resource budget 'Microsoft.Consumption/budgets@2026-06-01' = {
  name: name
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: { startDate: startDate }
    notifications: {
      actual25: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 25
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      actual50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      actual75: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 75
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
    }
  }
}
