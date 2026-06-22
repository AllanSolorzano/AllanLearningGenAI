# Scoring Rubric

Total: 1000 points

## Category 1: Infrastructure Discovery

| Item | Points |
| --- | ---: |
| Service mapping | 25 |
| Dependency mapping | 25 |
| Risk identification | 50 |

Total: 100

## Category 2: Agent Design

| Item | Points |
| --- | ---: |
| Multi-agent architecture | 50 |
| Tool abstraction | 50 |
| MCP integration | 50 |
| Memory/context handling | 50 |

Total: 200

## Category 3: Chaos Planning

| Item | Points |
| --- | ---: |
| Hypothesis quality | 50 |
| Blast radius design | 50 |
| Safety checks | 50 |

Total: 150

## Category 4: Execution

| Item | Points |
| --- | ---: |
| Correct experiment | 50 |
| Safe execution | 50 |
| Rollback awareness | 50 |

Total: 150

## Category 5: Observability

| Item | Points |
| --- | ---: |
| Metrics usage | 25 |
| Logs usage | 25 |
| Traces usage | 25 |
| Event usage | 25 |

Total: 100

## Category 6: RCA

| Item | Points |
| --- | ---: |
| Accuracy | 50 |
| Root cause | 50 |
| Timeline | 25 |
| Recommendations | 25 |

Total: 150

## Category 7: Executive Communication

| Item | Points |
| --- | ---: |
| CTO summary | 25 |
| Business impact | 25 |

Total: 50

## Bonus Points

| Bonus | Points |
| --- | ---: |
| Fully autonomous experiment creation | 50 |
| Dynatrace integration | 50 |
| MCP-based tooling | 50 |
| Human approval workflow | 50 |
| Agent Safety Officer | 50 |

## Penalties

| Penalty | Points |
| --- | ---: |
| No safety validation | -100 |
| Agent performs unauthorized action | -250 |
| Deletes workload | -500 |
| Deletes namespace | Disqualified |

## Judge Guidance

Award high scores to teams whose agents can explain why they chose an experiment and what evidence supports the conclusion. Award low scores to teams that only wrap `kubectl apply` in an LLM prompt.
