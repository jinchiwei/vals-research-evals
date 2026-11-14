# Literature search method and limits

Search/review date: 2026-11-14. Purpose: select scientifically defensible PCNSL research-agent tasks for the Vals Build Your Own Eval demonstration and check overlap with existing evaluations. This was a **focused scoping search**, not a registered, systematic, exhaustive, or independently replicated literature review.

## Recorded query plan and observed returns

The machine-readable plan is [lit-query-plan.json](lit-query-plan.json). It names PubMed, arXiv and Semantic Scholar and requests `max_results_per_query = 8`. The saved raw response lists were inspected and counted directly, in query order:

| Query / saved response | PubMed | arXiv | Raw returned records |
|---|---:|---:|---:|
| `primary central nervous system lymphoma MRI radiogenomics` — [query-0.json](../../exp/20261114_pcnsl-frontier-suite/literature/query-0.json) | 1 | 8 | 9 |
| `scientific research agent benchmark data analysis` — [query-1.json](../../exp/20261114_pcnsl-frontier-suite/literature/query-1.json) | 8 | 8 | 16 |
| `machine learning leakage radiomics patient validation` — [query-2.json](../../exp/20261114_pcnsl-frontier-suite/literature/query-2.json) | 8 | 8 | 16 |
| `scientific integrity agents benchmark statistical errors` — [query-3.json](../../exp/20261114_pcnsl-frontier-suite/literature/query-3.json) | 0 | 8 | 8 |
| **Total across four queries** | **17** | **32** | **49** |

These are **49 raw results, not 49 unique studies or 49 included papers**. Each record supplies title, authors, year, abstract, URL and a source field. Observed totals exceed eight because the saved lists contain records from multiple providers, with at most eight from each provider in each response; this describes the observed output rather than proving the search tool's internal cap semantics. No Semantic Scholar records appear in these saved lists despite its presence in the plan. The lists alone do not establish whether that provider returned no matches, failed, or was omitted. Preserve the raw files and query plan together rather than claiming all three planned databases were successfully searched.

No deduplicated unique-record total, formal exclusion count, full-text screening denominator, inter-reviewer screening agreement, or PRISMA flow is claimed. The source registries below describe verified selected sources; they are not a substitute for every raw search response. Some literature was found through supplementary primary-source searches rather than these four broad queries.

## Supplementary searches and source verification

Two workstreams expanded the initial results:

1. **PCNSL/domain:** MRI radiogenomics; MYD88, CD79B and IRF4; related but distinct endpoints such as BCL6 rearrangement and Ki-67; imaging acquisition/feature definitions; assay interpretation; clinical timing; small-sample validation and reporting standards. Official dataset registry/tutorial/landing-page evidence was reviewed separately from papers.
2. **Evaluation/methodology:** InfiAgent-DABench, DSBench, MLAgentBench, ScienceAgentBench, MLGym, RE-Bench, MLE-bench, BLADE, Scientist-Bench, PaperBench, AstaBench, ReplicatorBench, SciIntegrity-Bench and PAPERBENCHX; leakage, selection bias, uncertainty and evaluation integrity. Benchmark names, titles and basic scope were verified against primary papers or official repositories rather than assumed from secondary lists.

Search results were followed to publisher pages, PubMed, arXiv abstracts, accessible primary full text, official project repositories and official guidelines. Secondary summaries were not used as substitutes for primary claims. Access depth varies: an abstract supports reported cohort/input/endpoint/results but generally cannot establish all preprocessing, selection or leakage details. Repository evidence is labeled as software/project documentation; preprint status and author-reported results are not silently upgraded to independent validation.

An absent result in this search is not evidence that no paper or public dataset exists. For example, failure to verify a direct MRI-to-IRF4 study or a suitable external genotype-labeled PCNSL MRI cohort is a search limitation/resource gap, not a universal negative finding.

## Retained source registries

- [pcnsl-sources.json](pcnsl-sources.json): domain sources, official dataset references, evidence-access notes and limitations. Narrative synthesis: [pcnsl-literature.md](pcnsl-literature.md).
- [evaluation-sources.json](evaluation-sources.json): 22 selected primary paper/project/guideline sources with verification scope, contribution and limitations. Narrative synthesis: [evaluation-literature.md](evaluation-literature.md).
- [valkyrie-integration.md](valkyrie-integration.md): separate current software verification against official source commit `1fe5c33d8c625540b1ea4f71e5ec159c1d813b48`, installed CLI `2026.11.12.2` and SDK `0.34.0`. This is implementation documentation, not a scientific-study search result.

Registry entries can overlap across workstreams. Their counts must not be added and called unique included studies without deduplication. Common standards and uncertainty papers legitimately inform both reviews. No bibliography count is a measure of evidentiary strength.

## Selection and extraction policy

Sources were prioritized when they changed a concrete design decision: endpoint semantics, available modalities/outcomes, independent evaluation, small-sample uncertainty, executable grading, fair compute/tool access, integrity controls, or the novelty boundary. Direct genotype studies were distinguished from diagnosis, prognosis, expression, methylation and treatment-response work. Official dataset advertisements were distinguished from verified archive contents.

For clinical studies, extraction recorded cohort size and source, input modality, endpoint, evaluation design, reported result, and the limit imposed by accessible text. Reported AUROC values were not pooled: cohorts, endpoints, splits and selection procedures differ. No meta-analysis, pooled predictive-performance estimate, formal risk-of-bias scoring exercise, or conclusion that imaging reliably predicts a given mutation was performed.

For agent benchmarks, extraction recorded task scope, executable environment, reference/grading approach, controls and relevance. Historical model scores were treated as dated configuration-specific results. They do not demonstrate that current frontier systems fail our tasks. Current local pilot outcomes—so far all passing the tested families—take precedence over expectations based on older benchmark difficulty.

## Known limits and appropriate use

The search is time-limited and English-query dominated; it may miss non-indexed, non-English, newly published or differently named work. Query expansion was adaptive rather than preregistered. Selection was relevance-driven, not blinded double screening. Some sources are conference abstracts or recent preprints. Full methods and supplementary materials were not available for every study, and no claim of exhaustive full-text review is made.

No patient records, signed download links, credentials or unpublished clinical tables were sent to search services in these literature workstreams. This statement concerns the literature review, not a substitute for the separate hosted-data audit.

Use the review to motivate and constrain tasks and to avoid unsupported novelty claims. It cannot establish a new clinical biomarker, public-release equivalence, complete data permissions, contamination-free evaluation, or a frontier-model failure. The consolidated task design and its current empirical limitations are in [benchmark-design.md](benchmark-design.md).
