# AI Bills Database: Comprehensive Documentation (v2)

## Overview

This database represents a complete pipeline for analyzing U.S. state-level artificial intelligence legislation from 2019–2026. The system integrates automated web scraping, API enrichment, feature engineering, and multi-agent AI analysis to transform raw legislative text into structured, actionable insights. The final dataset contains 2,571 AI and deepfake-related bills across all 50 U.S. states, enhanced with political context, regional clustering, and sophisticated multi-dimensional policy analysis.

## Purpose and Research Context

The database supports quantitative political science research on AI policy diffusion, legislative patterns, and state responsiveness to emerging technology governance challenges. It enables:

- **Policy Diffusion Analysis**: Understanding how AI legislation spreads across states and partisan boundaries
- **Spatial Econometric Modeling**: Examining geographic clustering and regional influence patterns
- **Legislative Success Prediction**: Analyzing factors that determine bill outcomes
- **Comparative Policy Analysis**: Evaluating bills across consistent policy dimensions

## Data Acquisition

### Primary Data Sources

The database consolidates legislation from five primary sources via the National Conference of State Legislatures (NCSL):

1. **AI Legislation 2019–2022**
   - Source: https://www.ncsl.org/technology-and-communication/legislation-related-to-artificial-intelligence
   
2. **Deepfakes 2024 Legislation**
   - Source: https://www.ncsl.org/technology-and-communication/deceptive-audio-or-visual-media-deepfakes-2024-legislation
   
3. **AI 2024 Legislation**
   - Source: https://www.ncsl.org/technology-and-communication/artificial-intelligence-2024-legislation

4. **AI 2025 Legislation**
   - Source: https://www.ncsl.org/technology-and-communication/artificial-intelligence-2025-legislation

5. **AI 2025–2026 Legislation**
   - Source: https://www.ncsl.org/financial-services/artificial-intelligence-legislation-database
      - The corpus was updated to include bills introduced or carried over into the 2026 legislative session, extending coverage through April 2026.

### Supplementary Data Sources

**Political Control Data**
- Source: National Conference of State Legislatures (NCSL) State Partisan Composition database
- URL: https://www.ncsl.org/about-state-legislatures/state-partisan-composition
- Coverage: Year-specific legislative partisan control for 2019–2026

**Sponsor Metadata**
- Source: LegiScan API
- Purpose: Enrichment of sponsor names and party affiliations for all datasets

### Web Scraping Process

The acquisition pipeline proceeded in two stages:

**Stage 1: Landing Page Scraping**

Extracted from NCSL topic landing pages:
- `Jurisdiction`: State or territory name
- `Bill_Number`: Legislative identifier (e.g., HB 208, SJR 14)
- `Bill_Title`: Official bill title
- `Bill_Status`: Current legislative status
- `NCSL_Summary`: Brief description from NCSL
- `NCSL_Category`: Topic categorization (when available)
- `Bill_URL`: Link to detailed bill page

**Stage 2: Bill Detail Page Scraping**

For each valid `Bill_URL`, the system extracted:

- **Version_Date**: Latest version date, normalized to MM/DD/YYYY format
- **Bill_Text**: Full legislative text with extensive cleaning:
  - Removed UI artifacts ("View in PDF", "Added", "Deleted", "Vetoed")
  - Stripped footer elements ("Cookies", "Privacy Policy", "Terms & Conditions")
  - Eliminated copyright notices and page artifacts
- **Sponsor Information** (AI 2025 only): Direct extraction of `Sponsor` and `Sponsor_Party` as JSON lists from bill pages

### Derived Fields from Acquisition

**Year Extraction**
- Derived from `Version_Date` using pattern matching
- Example: "02/06/2025" → 2025

**Measure Code Derivation**
- Extracted from `Bill_Number` prefix
- Examples: "HB 208" → HB, "SJR 14" → SJR, "H 123" → H
- Standardizes measure type across jurisdictions

## Data Cleaning and Preprocessing

### Quality Control Filters

The pipeline applied rigorous filters to ensure data integrity and suitability for AI analysis:

**Filter 1: Completeness Check**
- Dropped rows missing `Bill_Number` (essential for identification)
- Dropped rows missing `Bill_Text` (required for analysis)

**Filter 2: Text Length Constraints**
- Minimum threshold: 1,500 characters (ensures substantive content)
- Maximum threshold: 40,000 characters (optimizes multi-agent processing)
- Rationale: Balances content richness with computational efficiency

**Filter 3: Sponsor Completeness**
- Required both `Sponsor` and `Sponsor_Party` fields after enrichment
- Dropped rows with incomplete sponsor metadata

### Sponsor Enrichment via LegiScan API

For all datasets lacking sponsor information from scraping, an enrichment process queried the LegiScan API:

**Methodology:**

1. **State Code Mapping**: Normalized `Jurisdiction` to two-letter codes (e.g., Vermont → VT)

2. **Bill Number Variant Generation**: Created multiple search variants to maximize match rates:
   - Space variants: "S 177", "S177"
   - Hyphenated: "S-177"
   - Zero-padded: "H0365"
   - Chamber prefixes: Added "B" suffix where appropriate (H → HB, S → SB)

3. **API Query Process**:
   - Authenticated using environment variable `LEGISCAN_KEY`
   - Implemented throttling to respect rate limits
   - Iteratively tested variants until match found

4. **Data Extraction**:
   - `Sponsor`: JSON array of sponsor names (preserves order)
   - `Sponsor_Party`: JSON array of party codes aligned with sponsors

### Text Cleaning Standards

Bill text underwent comprehensive cleaning to remove non-legislative content:

- **UI Elements**: Removed web interface controls and navigation artifacts
- **Legal Boilerplate**: Stripped standard footer language and copyright notices
- **Formatting Normalization**: Standardized whitespace and line breaks
- **Version Indicators**: Removed version tracking metadata from display text

## Feature Engineering

### Feature 1: State Political Control

**Field Name**: `State_Political_Control`

**Description**: Year-specific classification of state legislative partisan control

**Methodology**:
- Cross-referenced each bill's state and year with NCSL political composition data
- Created year-specific lookup tables for 2019–2026
- Mapped bills to contemporary political environment at time of proposal

**Classification Values**:
- `R`: Republican control of both legislative chambers
- `D`: Democratic control of both chambers
- `Div`: Divided control (split chambers or frequently changing)
- `Unknown`: Unmapped jurisdictions (territories, special cases)

This temporal precision enables accurate causal modeling by preventing political control misattribution.

### Feature 2: Regional Cluster ID

**Field Name**: `Regional_Cluster_ID`

**Description**: Geographic and political regional groupings designed for spatial econometric analysis

**Methodology**:
- Based on U.S. Census regions with political science modifications
- Texas isolated as separate region due to unique political-economic characteristics
- Optimized for spatial weights matrix construction

**Regional Classifications**:

| Region | States | Bill Count | Percentage |
|--------|--------|------------|------------|
| **Northeast** | CT, ME, MA, NH, RI, VT, NJ, NY, PA | 729 | 28.4% |
| **Southeast** | DE, DC, FL, GA, MD, NC, SC, VA, WV, KY, TN, AL, MS, AR, LA | 674 | 26.2% |
| **West** | AZ, CO, ID, MT, NV, NM, UT, WY, AK, CA, HI, OR, WA | 554 | 21.5% |
| **Midwest** | IL, IN, MI, OH, WI, IA, KS, MN, MO, NE, ND, SD | 476 | 18.5% |
| **Texas** | TX, OK | 138 | 5.4% |

### Feature 3: Bill Status Grouped

**Field Name**: `Bill_Status_Grouped`

**Description**: Simplified three-category classification of legislative outcome derived from the detailed `Bill_Status` field

**Methodology**:
- Collapsed the many `Bill_Status` variants (e.g., "Enacted - Act No. 184", "Failed - Adjourned", "Pending - Carryover") into three outcome categories based on prefix matching

**Classification Values**:

| Group | Includes | Count | Percentage |
|-------|----------|-------|------------|
| **Passed** | Enacted, Adopted, To Governor | 370 | 14.4% |
| **Failed** | Failed, Vetoed (all variants) | 766 | 29.8% |
| **Pending** | Pending, Override Pending (all variants) | 1,435 | 55.8% |

For enactment rate analyses, "resolved" bills are defined as the union of Passed and Failed (n=1,136), excluding Pending bills.

## AI-Driven Data Generation: Multi-Agent Analysis System

### System Architecture

The database incorporates AI-generated policy analysis through a sophisticated multi-agent system built using LangGraph and LangChain. The architecture implements a "Graph of Graphs" design where specialized agents operate as independent subgraphs with coordinated workflows.

**Core Technologies**:
- **LangGraph**: State management and multi-agent workflow orchestration
- **LangChain**: Agent interaction abstractions and LLM integration
- **Pydantic**: Schema validation, structured output parsing, and data integrity enforcement
- **Pandas**: CSV I/O operations and data transformation

**LLM Models**:
- **Extractor and Summarizer agents**: `gpt-4o-mini` (temperature=0)
- **Analyst and Judge agents**: `gpt-5-nano` (temperature=0)

### Keyword Pre-Filter

Before entering the multi-agent pipeline, each bill passes through a non-LLM keyword filter that screens bill text for AI-specific terminology. This filter serves as a cost-efficient gate, preventing bills with no AI relevance from consuming agent API calls.

**Filter Methodology**:
- Searches the full bill text for AI-specific terms including: "artificial intelligence", "machine learning", "deep learning", "neural network", "large language model", "generative AI", "foundation model", "algorithmic discrimination", "deepfake", "facial recognition", "autonomous vehicle", "automated decision system", and "AI" as a word-boundary token
- Bills with no matching terms are immediately assigned zero scores across all seven dimensions and bypass the agent pipeline
- The keyword list intentionally excludes broader technology terms (e.g., "algorithm", "automated system", "digital replica") that trigger false positives on non-AI legislation

**Filter Results**:
- 484 of 2,571 bills (18.8%) were blocked by the keyword filter
- Filtered bills receive `status: "filtered_not_ai"` with all seven dimension scores set to 0
- The remaining 2,087 bills (81.2%) proceeded to full agent analysis

### Agent Specialization and Workflow

The system employs seven specialized analyst agents, each focused on a distinct policy dimension, plus a quality assurance judge agent:

#### Analyst 1: Product Safety, Risk, & Accountability
**Dimension**: Rules to ensure that an AI product is safe for its users, to protect them, to ensure it is reliable, not deceptive, mitigates inherent risks (like bias), and assigns responsibility for failures

**Analysis Focus**:
- Model safety testing and reliability standards
- Bias detection and algorithmic auditing
- Transparency (explainability, logging, disclosure)
- Liability and responsibility for harms
- Security and adversarial robustness requirements
- Incident reporting and monitoring systems

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Analyst 2: AI Inputs & IP
**Dimension**: Rules focused on fair and legal economic rights in the creation of AI products and the supply chain, managing ownership, compensation, intellectual property, data usage rights, and consumer profiling

**Analysis Focus**:
- Training data compensation and copyright
- Intellectual property and right of publicity
- Data privacy and consumer profiling rights
- Model output attribution and disclosure
- Creator compensation mechanisms
- Data ownership and portability rights

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Analyst 3: Market Structure & Competition
**Dimension**: Rules focused on the market environment of the AI industry, to ensure a competitive market, addressing market concentration, access to resources, and fair competition

**Analysis Focus**:
- Data access and sharing requirements
- Computing resource allocation and interoperability
- Platform governance and antitrust oversight
- Market concentration limits
- Merger and acquisition oversight
- Restrictions on vertical integration
- Application of essential facilities doctrine

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Analyst 4: Sectoral Use & Application
**Dimension**: Rules focused on the deployment and use of AI, applying restrictions, specific mandates, permissions, or prohibitions for the use of AI tools in specific sectors or situations

**Analysis Focus**:
- High-risk systems (healthcare, finance, housing)
- Employment and workforce management (Automated Employment Decision Tools — AEDTs)
- Public sector deployment and procurement guidelines
- Content misinformation and deepfake bans/disclosure
- Human-in-the-loop and human oversight requirements
- Sector-specific deployment standards (education, legal, insurance)
- Automated decision-making rights and appeals processes

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Analyst 5: Existential & Societal Risk
**Dimension**: Rules focused on long-term, broad consequences like job displacement, environmental concerns, and effects on democratic processes

**Analysis Focus**:
- Labor market transition and job displacement policy
- Energy, environmental impact, and efficiency
- Democratic process and election security
- Social equity and digital divide considerations
- Educational system adaptations
- Cultural heritage and language preservation
- Community impact assessments

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Analyst 6: Institutional Framework & Processes
**Dimension**: Rules focused on rule-making frameworks, for managing the development and/or deployment of AI, including the creation of study bodies, advisory councils, and regulatory testing environments

**Analysis Focus**:
- Task forces, advisory councils, and studies
- Regulatory sandboxes and innovation policy
- Government agency policy development
- Agency rulemaking authority and mandates
- Research and reporting requirements
- Interstate coordination and compacts
- Enforcement mechanisms and penalties
- Definitions, scope, and applicability provisions

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Analyst 7: AI Advancement and Development
**Dimension**: Rules focused on fiscal action, including appropriations, grants, tax incentives, and direct investment in AI infrastructure or training

**Analysis Focus**:
- Direct appropriations for R&D/projects
- Tax incentives and economic grants
- Workforce training and education funding
- Critical infrastructure and computing investment
- Public-private partnerships
- Innovation hub development
- Research grant programs

**Scoring Rubric** (0/0.5/1 scale):
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

#### Judge Agent: Quality Assurance
**Role**: Multi-dimensional quality control and consistency enforcement

**Evaluation Criteria**:
- Accuracy of scoring relative to bill content
- Consistency of justifications with scores
- Completeness of dimensional analysis
- Adherence to rubric standards
- Clarity and coherence of summaries

**Workflow Integration**:
- Reviews all analyst outputs before finalization
- Provides structured feedback identifying deficiencies
- Triggers revision cycles when quality thresholds not met
- Ensures cross-bill consistency in scoring methodology

### Multi-Agent Processing Workflow

**Step 1: Keyword Pre-Filter**
- Non-LLM filter screens bill text for AI-specific terminology
- Bills failing the filter receive auto-zero scores and bypass the agent pipeline
- 484 of 2,571 bills (18.8%) blocked at this stage

**Step 2: Intelligent Extraction**
- Extractor agent (`gpt-4o-mini`) identifies and extracts most relevant bill sections
- Focuses on substantive policy provisions
- Filters procedural and administrative text
- Outputs to `bill_extracts` column

**Step 3: Summary Generation**
- Summarizer agent (`gpt-4o-mini`) synthesizes bill into concise 5-sentence plain-language summary
- Accessible to non-expert audiences
- Captures core policy mechanisms and implications
- Outputs to `summary` column

**Step 4: Sequential Dimensional Analysis**
- Seven analyst agents (`gpt-5-nano`) process each bill sequentially
- Each generates a dimension-specific score (0/0.5/1) with detailed justification
- Agents operate independently using specialized prompts and rubrics
- Results stored in `analyst_results` JSON

**Step 5: Quality Review**
- Judge agent (`gpt-5-nano`) evaluates all outputs holistically
- Assesses scoring accuracy, justification quality, and consistency
- Provides granular feedback for improvement
- Tracks revisions in `retry_attempts` column

**Step 6: Iterative Revision** (if needed)
- Flagged analyses return to respective analyst agents
- Revisions address specific judge feedback
- Process repeats until quality standards met or maximum retry limit reached
- Retry counts tracked per analyst

**Step 7: Structured Output**
- Validated results written to CSV with standardized schema
- Processing status tracked in `status` column (`completed`, `filtered_not_ai`, or `error`)
- All 29 columns populated for successful analyses

### Generated Columns

The multi-agent system produces the following analysis for each bill, stored in the `analyst_results` column as a JSON object containing scores and justifications for all seven policy dimensions. To enable direct querying and analysis, these scores have been extracted into 7 separate flattened columns.

**Multi-Agent Analysis Structure:**

Each bill receives:
- **7 dimensional scores** (0/0.5/1 scale): `product_safety_score`, `ai_inputs_ip_score`, `market_structure_score`, `specific_use_score`, `societal_risks_score`, `institutional_processes_score`, `ai_advancement_score`
- **7 detailed justifications**: Text explanations for each dimensional score (stored in `analyst_results` JSON)
- **Bill extracts**: Most relevant sections identified by the Extractor agent
- **Plain-language summary**: Accessible 5-sentence summary from the Summarizer agent

**Scoring Scale:**

All seven dimensions use a three-point scale:
- **0**: Not relevant — dimension not addressed in the bill
- **0.5**: Secondary relevance — relevant provisions present but dimension is not a primary focus
- **1**: Primary relevance — bill's central purpose addresses the dimension

For substantive analyses, scores are binarized (0.5 → 0) to focus on bills with primary dimensional focus.

**Flattened Score Columns (7 total):**

| Column | Dimension (Paper Name) | Data Type |
|--------|------------------------|-----------|
| `product_safety_score` | Product Safety, Risk, & Accountability | Float (0/0.5/1) |
| `ai_inputs_ip_score` | AI Inputs & IP | Float (0/0.5/1) |
| `market_structure_score` | Market Structure & Competition | Float (0/0.5/1) |
| `specific_use_score` | Sectoral Use & Application | Float (0/0.5/1) |
| `societal_risks_score` | Existential & Societal Risk | Float (0/0.5/1) |
| `institutional_processes_score` | Institutional Framework & Processes | Float (0/0.5/1) |
| `ai_advancement_score` | AI Advancement and Development | Float (0/0.5/1) |

**Additional Analysis Columns:**
- `bill_extracts` (String): Relevant bill sections extracted by the Extractor agent
- `summary` (String): Plain-language bill summary generated by the Summarizer agent
- `analyst_results` (JSON Object): Original nested JSON containing all scores and detailed justifications
- `retry_attempts` (JSON Object): Revision tracking per analyst agent (keys = analyst names, values = retry counts; absent keys indicate no revisions)
- `status` (String): Processing status indicator — `completed` (full agent pipeline), `filtered_not_ai` (keyword filter rejection), or `error` (processing failure)

## Validation Study

A stratified validation study assessed system–human agreement on a 91-bill sample drawn from the full corpus:

- **Sample composition**: 83 AI-related bills and 8 non-AI control bills, stratified across the seven taxonomy dimensions to ensure representation of each policy area
- **Annotators**: 3 trained undergraduate research assistants who independently scored each bill on the same 0/0.5/1 scale (binarized to 0/1 for agreement analysis)
- **Per-annotator system–human agreement**: Averaged 83.1% across all dimensions, with per-dimension agreement falling within a few percentage points of the inter-annotator ceiling
- **Unanimous-subset agreement**: On bills where all three annotators agreed, system–human agreement ranged from 85.5% to 100% depending on the dimension
- **Non-AI detection**: The system correctly identified all 8 non-AI control bills (8/8); two of three annotators also achieved 8/8, while one annotator scored 6/8
- **Conclusion**: The system performs comparably to trained human annotators, with agreement rates approaching the inter-rater reliability ceiling

Full validation methodology, inter-annotator agreement statistics, and per-dimension breakdowns are reported in the accompanying paper (Bhargava and Soliman, in preparation).

## Final Database Schema

### Complete Column Dictionary

| Column | Source | Description | Data Type |
|--------|--------|-------------|-----------|
| `Bill_Number` | NCSL Scrape | Legislative identifier (e.g., HB 208, SJR 14) | String |
| `measure_code` | Derived | Measure type from Bill_Number (HB, SB, SJR, etc.) | String |
| `Bill_Title` | NCSL Scrape | Official bill title | String |
| `Jurisdiction` | NCSL Scrape | State or territory name | String |
| `NCSL_Summary` | NCSL Scrape | Original NCSL summary | String |
| `NCSL_Category` | NCSL Scrape | Topic categorization (when available) | String |
| `Bill_URL` | NCSL Scrape | URL to bill detail page | URL |
| `Version_Date` | NCSL Scrape | Latest version date (MM/DD/YYYY) | Date |
| `Year` | Derived | Year from Version_Date | Integer |
| `Bill_Status` | NCSL Scrape | Legislative status (see status guide below) | String |
| `State_Political_Control` | Feature Engineering | Year-specific legislative control (R/D/Div) | String |
| `Regional_Cluster_ID` | Feature Engineering | Geographic-political region | String |
| `Bill_Text` | NCSL Scrape | Cleaned full bill text | String |
| `Sponsor` | NCSL/LegiScan | JSON list of sponsor names | JSON Array |
| `Sponsor_Party` | NCSL/LegiScan | JSON list of party codes | JSON Array |
| `Introduction_Date` | NCSL Scrape | Bill introduction date | Date |
| `bill_extracts` | Multi-Agent AI (Extractor) | Relevant bill sections extracted for analysis | String |
| `summary` | Multi-Agent AI (Summarizer) | Plain-language bill summary | String |
| `analyst_results` | Multi-Agent AI | JSON object with all scores and justifications | JSON Object |
| `retry_attempts` | Multi-Agent AI (Judge) | JSON tracking revisions per analyst (analyst: retry_count) | JSON Object |
| `status` | Multi-Agent AI | Processing status (completed/filtered_not_ai/error) | String |
| `product_safety_score` | Multi-Agent AI (extracted) | Product Safety, Risk, & Accountability | Float (0/0.5/1) |
| `ai_inputs_ip_score` | Multi-Agent AI (extracted) | AI Inputs & IP | Float (0/0.5/1) |
| `market_structure_score` | Multi-Agent AI (extracted) | Market Structure & Competition | Float (0/0.5/1) |
| `specific_use_score` | Multi-Agent AI (extracted) | Sectoral Use & Application | Float (0/0.5/1) |
| `societal_risks_score` | Multi-Agent AI (extracted) | Existential & Societal Risk | Float (0/0.5/1) |
| `institutional_processes_score` | Multi-Agent AI (extracted) | Institutional Framework & Processes | Float (0/0.5/1) |
| `ai_advancement_score` | Multi-Agent AI (extracted) | AI Advancement and Development | Float (0/0.5/1) |
| `Bill_Status_Grouped` | Derived | Simplified status grouping | String |

**Dataset Dimensions**: 2,571 rows × 29 columns

### Bill Status Classification Guide

**Active/In-Process Bills**:
- **Pending**: Bills currently in legislative process (committee, floor votes, between chambers)
- **Pending - Carryover**: Bills carried to next session without final action
- **To Governor**: Passed both chambers, awaiting executive action

**Unsuccessful Bills**:
- **Failed - Adjourned**: Died when session ended without final action
- **Failed**: Explicitly rejected via committee or floor vote

**Successful Bills**:
- **Enacted**: Became law after passage and gubernatorial signature
- **Adopted**: Passed (typically resolutions); includes non-binding measures

**Executive Action**:
- **Vetoed**: Rejected by governor after legislative passage
- **Override Pending**: Vetoed bill subject to legislative override attempts

## Research Applications

### Spatial Econometric Modeling

Regional clustering and political features support advanced spatial methods:

- **Spatial Weight Matrices**: Regional clusters provide meaningful neighborhood definitions
- **Geographic and Political Mechanisms**: Within-region control variation enables dual-channel analysis
- **Spillover Effects**: Cross-regional patterns reveal both geographic and partisan influence

### Legislative Success Prediction

Multi-dimensional analysis enables success factor identification:

- **Control Type Variation**: Sufficient distribution across R/D/Div for logistic regression
- **Contextual Factors**: Time-varying political environment for accurate modeling
- **Policy Content Predictors**: Seven-dimensional scores as independent variables

### Comparative Policy Analysis

Structured scoring enables systematic bill comparison:

- **Dimensional Profiles**: Bills characterized by consistent 7D policy vectors
- **Trend Identification**: Temporal and geographic patterns in policy emphasis
- **Outlier Detection**: Bills with unusual dimensional combinations
- **Evolution Over Time**: Eight-year span (2019–2026) reveals shifting regulatory priorities

## Reproducibility and Data Access

### Input Files
- **Original Corpus (2019–2025)**: `FULL_OLD_bills_part.csv` (1,531 × 18) — bills from NCSL AI 2019–2022, Deepfakes 2024, AI 2024, and AI 2025 sources
- **New Bills (2025–2026)**: `FULL_NEW_bills_only.csv` (1,040 × 17) — additional bills from updated 2025–2026 scrape
- **Combined Input**: `FULL_COMBINED_bills_part.csv` (2,571 × 17) — merged corpus prior to analysis pipeline
- **Batch Files**: `bills_part_1.csv` through `bills_part_7.csv` — combined input split into batches for processing
- **Final Dataset**: `Final_Database_10.csv` (2,571 × 29) — fully analyzed output

### Code Repository
Multi-Agent System Codebase: https://github.com/marksoliman3/Bill_Analyst_Agent

### Reproduction Steps

**Phase 1: Data Acquisition**
1. Run NCSL scrapers for AI 2019–2022, Deepfakes 2024, AI 2024, AI 2025, and AI 2025–2026
2. Concatenate raw outputs into single CSV
3. Apply completeness filters (drop missing Bill_Number/Bill_Text)
4. Apply length filters (1,500 ≤ Bill_Text length ≤ 40,000)

**Phase 2: Enrichment**
1. Execute LegiScan API enrichment for all datasets
2. Populate Sponsor and Sponsor_Party fields
3. Apply sponsor completeness filter

**Phase 3: Feature Engineering**
1. Map State_Political_Control using year-specific NCSL data (2019–2026)
2. Assign Regional_Cluster_ID based on geographic groupings
3. Validate temporal accuracy of political control assignments

**Phase 4: AI Analysis**
1. Configure multi-agent system with OpenAI API credentials
2. Bills pass through keyword pre-filter (484 blocked, 2,087 proceed)
3. Process remaining bills through seven-analyst workflow
4. Apply judge-based quality assurance with iterative revision
5. Export final analyzed dataset

### Prerequisites
- Python 3.10+
- OpenAI API key (stored in `.env` as `OPENAI_API_KEY`)
- LegiScan API key (stored in `.env` as `LEGISCAN_KEY`)
- Required packages: pandas, langchain, langgraph, langchain-openai, pydantic, tenacity, python-dotenv

## Known Limitations and Edge Cases

### Data Acquisition
- Some jurisdictions use non-standard bill numbering requiring variant generation
- LegiScan coverage gaps for certain bills/jurisdictions resulted in <1% exclusions
- Text length constraints excluded very short procedural bills and extremely lengthy omnibus bills

### Feature Engineering
- Territories and non-state jurisdictions mapped to "Unknown" categories
- Political control classification simplified to three categories (nuanced coalitions collapsed)
- Regional clusters aggregate diverse states (e.g., Alaska and California both "West")

### AI Analysis
- Multi-agent scoring reflects model training biases and prompt engineering choices
- Dimensional boundaries sometimes ambiguous (e.g., market vs. societal impacts overlap)
- Summary quality varies with bill complexity and legal terminology density
- The keyword pre-filter intentionally excludes broader technology terms, which may cause a small number of AI-adjacent bills to be filtered out

## Data Attribution and Licensing

### Source Attributions
- **NCSL Data**: Legislative metadata and bill text courtesy of National Conference of State Legislatures
- **LegiScan Data**: Sponsor enrichment via LegiScan API; attribution required per LegiScan terms
- **Political Control Data**: State partisan composition from NCSL official records

### Intended Use
This dataset is designed for academic research, policy analysis, and AI governance studies. Commercial use should respect source data licensing requirements.

### Citation

Bhargava, H. K., & Soliman, M. (in preparation). The Structure of U.S. State AI Policy: Evidence from a Multi-Dimensional Bill Classification.

When using this database, please cite both the paper and the original NCSL sources. Multi-agent analysis components should reference the Bill Analyst system codebase.

---
