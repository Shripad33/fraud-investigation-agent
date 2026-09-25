# Fraud Investigation Agent — Hacker House Goa

An explainable fraud investigation agent built for the Hacker House Goa challenge.

## What It Does

The system investigates suspicious financial transactions using:

- Transaction history
- Customer behavior
- Identity and device evidence
- Cross-customer activity
- Similar transaction patterns
- Historical closed fraud cases
- Rule-based investigation decisions
- TigerGraph relationship modeling

The investigation produces an explainable case record containing evidence, findings, decisions, actions, and recommended next steps.

## Architecture

```text
Case Pack
   |
   v
Investigation Agent
   |
   +--> Transaction History
   |
   +--> Customer Behavior
   |
   +--> Identity / Device Evidence
   |
   +--> Historical Closed Cases
   |
   +--> Cross-Customer Activity
   |
   v
Evidence Analysis
   |
   v
Fraud Decision
   |
   +--> Verdict
   +--> Fraud Probability
   +--> Pattern
   +--> Exposure
   +--> Next Best Action
   +--> Evidence Requests
   +--> SAR Assessment
   |
   v
Case Investigation JSON
