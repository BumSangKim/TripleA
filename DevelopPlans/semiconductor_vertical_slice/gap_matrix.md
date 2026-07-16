# SEM-001 Semiconductor Gap Matrix

Status meanings: `READY` reusable now; `EXTEND` reusable contract needs a
semiconductor-specific extension; `PARTIAL` related capability exists but does
not satisfy the slice contract; `MISSING` no identified implementation;
`BLOCKED_BY_OWNER_DECISION` requires a business/activation choice.

| Target component | Status | Evidence | Safe next action | Owner/activation note |
|---|---|---|---|---|
| Canonical semiconductor IDs | EXTEND | `asset_master.yml`, selector rules, existing monitor-only references | Define slice-local IDs/roles using the existing universe schema | Do not activate existing order selectors. |
| Semiconductor raw metric catalog | MISSING | Generic capex raw contracts exist only | Add fixture-first metric catalog and PIT raw-data contract | Metric definitions/source ownership must be explicit. |
| Global demand features | PARTIAL | AI CAPEX/token feature builder | Add semiconductor-specific input mapping without changing AI CAPEX behavior | Diagnostic-only. |
| Memory price features | MISSING | Memory-cycle coverage is not a price feature contract | Add PIT fixture and feature contract | Do not infer missing market rules. |
| Inventory and supply features | MISSING | Generic quality/snapshot contracts only | Add source/fixture schema and conservative fallback | Require data-owner provenance. |
| Equipment and capacity features | MISSING | Capex/company metric raw contracts | Add fixture-based feature contract | No source or weighting invention. |
| Earnings and quality features | PARTIAL | `RawCompanyMetricPoint`, quality metadata | Define semiconductor fields and materialization | Preserve generic data model. |
| Market features | PARTIAL | `CommonSectorScoringEngine` price-history reader | Add diagnostic market-feature adapter | Preserve current common scoring behavior. |
| Macro fit/risk penalty | EXTEND | AI CAPEX macro overlay and macro distribution exist | Add non-activating semiconductor macro-fit contract | No macro threshold change. |
| Subsector scores | MISSING | No DRAM/NAND/foundry/equipment score contract found | Create diagnostic-only score contract | Candidate parameters must be versioned. |
| Sector/asset score aggregation | EXTEND | common aggregator and AI CAPEX components | Add independent semiconductor diagnostic aggregation | No active tilt wiring. |
| MSCI World benchmark ID | MISSING | No canonical MSCI World asset/config entry found | Add after universe task identifies a canonical benchmark source | Strategic policy is fixed by this task pack. |
| ETF/benchmark look-through | PARTIAL | sector portfolio configs have generic look-through controls | Add point-in-time holdings + overlap contract | Do not estimate holdings from current constituents. |
| Risk budget and active tilt | PARTIAL | `RiskBudgetEngine`, allocation ranges, sector tilt engine | Add a review-only proposal contract after scores/look-through exist | Active allocation change requires owner approval. |
| Rebalancing and hard constraints | PARTIAL | rebalancing service and account constraints exist | Consume only simulation-safe proposal output | Hard constraints remain blocking. |
| Point-in-time vertical-slice backtest | PARTIAL | generic runner, service boundary, leakage tests | Add deterministic fixture runner | No live data requirement. |
| Walk-forward/sensitivity/stress gates | PARTIAL | AI CAPEX shadow reports/tuning gates | Reuse gate shape for semiconductor fixtures | Historical promotion is later-only. |
| Audit/shadow handoff | EXTEND | audit/report contracts and AI CAPEX shadow artifacts | Add semiconductor diagnostic report schema | `production_ready` stays false. |

## Owner decisions not implied by this task

The following must stay `REVIEW_REQUIRED` until an explicit downstream task
provides source and policy evidence: real provider/source selection, exact
semiconductor metric definitions, benchmark holdings licensing, active tilt
limits, and production activation. The MSCI World core posture itself is the
target policy supplied by this task pack; its canonical repository identifier
is still missing.
