# 📊 Bill Analyst: AI-Powered Legislative Analysis

![Bill Analyst Banner](https://img.shields.io/badge/Bill%20Analyst-Intelligent%20Legislative%20Analysis-blue)

## 🔍 What is Bill Analyst?

**Bill Analyst** is a sophisticated yet easy-to-use tool that transforms complex legislative bills into clear, structured insights. It's like having a team of expert analysts working for you 24/7, breaking down dense legal text into actionable information.

### The Problem We Solve

Legislative bills are:
- 📚 **Lengthy and complex** (often 100+ pages of legal jargon)
- 🧩 **Difficult to compare** across different policy dimensions
- ⏱️ **Time-consuming to analyze** manually
- 🤔 **Inaccessible to non-experts** without legal backgrounds

### Our Solution

Bill Analyst uses artificial intelligence to:
- ✂️ **Extract the most relevant sections** from lengthy bills
- 📝 **Create plain-language summaries** anyone can understand
- 🏷️ **Score bills across key dimensions** using a consistent taxonomy
- 🔄 **Ensure quality through multi-agent review** and revision

## 🌟 Key Features

### 1. Intelligent Extraction
Our system identifies and extracts only the most relevant portions of bills, focusing on what matters most.

### 2. Human-Readable Summaries
Complex legal language is transformed into concise, clear summaries that anyone can understand.

### 3. Multi-Dimensional Analysis
Each bill is analyzed across four critical dimensions by specialized AI analysts:

| Dimension | What It Measures |
|-----------|------------------|
| 🏢 **Market Structure & Competition** | How the bill affects market dynamics, competition, and business operations |
| 🛡️ **Product Safety & Accountability** | How the bill addresses safety standards, testing, and accountability measures |
| 📜 **Property Rights & Attribution** | How the bill impacts intellectual property, data rights, and attribution |
| 🌍 **Societal Impact & Governance** | How the bill affects labor, environment, democratic processes, and social equity |

### 4. Quality Assurance
A specialized "Judge" agent reviews all analyses, providing feedback and triggering revisions when needed to ensure consistent, high-quality results.

### 5. Structured Output
Results are delivered in a clean, structured format that makes it easy to compare bills and identify trends.

## 💻 Technical Overview

Bill Analyst is built as a local Python application using state-of-the-art AI technologies:

- **LangGraph**: Powers our multi-agent workflow with sophisticated state management
- **LangChain**: Provides core abstractions for agent interactions
- **Pydantic**: Ensures data validation and schema enforcement
- **Pandas**: Handles all CSV operations for input and output

The system is designed as a "Graph of Graphs" where each specialized agent operates as its own subgraph, creating a modular, maintainable architecture.

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- OpenAI API key

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/your-organization/bill-analyst.git
   cd bill-analyst
   ```

2. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your OpenAI API key
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

### Running the Application

1. Place your input CSV file in the `data` directory (see format requirements below)

2. Run the application
   ```bash
   python -m src.main
   ```

3. Find your results in the `data` directory as `output_analysis.csv`

### Input Format

Your input CSV should contain at minimum these columns:
- `Bill_Number`: A unique identifier for each bill
- `Bill_Text`: The full text of the bill

## 📈 Example Output

For each bill, Bill Analyst produces:
- A concise 5-sentence summary in plain language
- Scores (0-3) across four key dimensions
- Detailed justifications for each score
- Processing status and metadata

## 🔒 Privacy & Security

Bill Analyst runs entirely on your local machine. Your legislative data never leaves your computer except for secure API calls to the language model.

## 📞 Support & Feedback

For questions, feature requests, or bug reports, please open an issue on our GitHub repository or contact our support team at support@billanalyst.ai.

---

<p align="center">
  <em>Bill Analyst: Making legislation transparent, accessible, and actionable.</em>
</p>
