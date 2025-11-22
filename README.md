# The Impact of News Sentiment on Stock Prices: An Econometric and NLP-Based Analysis

**Case Study: VN30 Index Constituents (Jan 2025 – Sep 2025)**

## 📌 Overview

This project investigates the causal relationship between financial news sentiment and stock returns for the 30 constituent companies of the VN30 Index (Vietnam). By integrating **Natural Language Processing (NLP)** with rigorous **Panel Data Econometrics**, this study aims to quantify how firm-specific and macroeconomic news sentiment influences market movements.

The pipeline automates data collection, sentiment scoring using **PhoBERT**, panel dataset construction, and comprehensive statistical testing (Fixed Effects, Random Effects, GMM, and Event Studies).

## 🚀 Key Features

  * **Automated Data Pipeline:** Scrapes news from major Vietnamese financial portals (e.g., CafeF) and fetches market data via `yfinance`.
  * **Advanced NLP:** Utilizes `wonrax/phobert-base-vietnamese-sentiment` (a Transformer-based model) for state-of-the-art sentiment classification in Vietnamese.
  * **Econometric Modeling:** Implements multiple panel regression models:
      * Pooled OLS
      * Fixed Effects (FE)
      * Random Effects (RE)
      * Arellano–Bond Dynamic Panel (GMM)
  * **Robust Diagnostics:** Includes a full suite of tests: Augmented Dickey-Fuller (Stationarity), Breusch-Pagan (Heteroskedasticity & Random Effects), Wooldridge (Autocorrelation), and Hausman Test.

## 🛠️ Installation & Requirements

Ensure you have Python 3.8+ installed. It is recommended to use a virtual environment.
## 📂 Project Structure

```
├── 459828.ipynb             # The primary notebook containing the full research pipeline (Steps 1-8)
├── scraper_utils.py       # Standalone module for crawling financial news
├── README.md              # Project documentation
└── data/                  # Directory for storing datasets
    ├── stock_prices_raw.csv
    ├── news_raw.csv
    ├── news_scored.csv
    └── panel_data.csv
```

## ⚙️ Research Pipeline (Step-by-Step)

The analysis in `459828.ipynb` is organized into sequential steps:

### **Step 1: Stock Data Collection**

  * Downloads **OHLCV** (Open, High, Low, Close, Volume) data for all 30 VN30 tickers + the E1VFVN30 ETF.
  * Computes daily Log Returns (`ret`) to ensure stationarity.
  * Source: Yahoo Finance API.

### **Step 2: News Data Collection**

  * Utilizes a custom crawler (`scraper_utils.py`) to parse sitemaps from financial news portals.
  * Filters articles based on timeframes and firm-specific keywords.
  * **Note:** This script can be run independently to fetch raw text data.

### **Step 3: Sentiment Analysis (NLP)**

  * Classifies news into **Firm-Specific** (e.g., "VCB profits rise") or **Macroeconomic** (e.g., "Inflation rates").
  * Applies **PhoBERT** to score headlines on a scale of -1 (Negative) to +1 (Positive).
  * Implements incremental checkpointing to avoid re-scoring existing data.

### **Step 4: Panel Data Construction**

  * Aggregates sentiment scores by `Ticker` and `Date`.
  * Merges financial data with sentiment data.
  * **Feature Engineering:**
      * Creates Lagged Variables ($t-1, t-2$) to capture delayed market reactions.
      * Creates Interaction Terms ($Sentiment \times Volume$) to test liquidity effects.
      * Normalizes trading volume.

### **Step 5: Econometric Modeling**

Estimates the primary regression models using Clustered Robust Standard Errors:

  * **Model 1A:** Basic Fixed Effects (Sentiment + Market Return).
  * **Model 1B (Main):** Advanced Fixed Effects (Includes Interaction terms & Volume).
  * **Model 2:** Dynamic Panel GMM (Arellano–Bond) to control for return persistence.
  * **VIF Analysis:** Checks for Multicollinearity among independent variables.

### **Step 6: Diagnostics & Robustness Checks**

Validates model assumptions through rigorous testing:

  * **Step 6A (Diagnostics):**
      * *ADF Test:* Confirms stationarity of returns.
      * *Breusch-Pagan (Heteroskedasticity):* Detects non-constant variance.
      * *Wooldridge Test:* Detects serial autocorrelation.
  * **Step 6B (Robustness):** Tests alternative lags ($t-2$) and compares FE vs. RE vs. Pooled OLS.
  * **Step 6E & 6F:** Performs specific manual calculations for Breusch-Pagan LM tests (comparing Random Effects vs. Pooled OLS) to handle library limitations.

### **Step 7: Visualization**

  * Plots rolling averages (7-day window) of Market Returns vs. Firm Sentiment vs. Macro Sentiment to identify visual correlations.

### **Step 8: Comparative Regression Table**

  * Generates a consolidated academic table comparing coefficients, standard errors, and significance levels across Pooled OLS, Random Effects, and Fixed Effects models.

## 📊 Methodology Summary

The primary equation estimated (Fixed Effects) is:

$$r_{i,t} = \alpha_i + \beta_1 SentFirm_{i,t-1} + \beta_2 SentMacro_{t-1} + \delta_1 r_{m,t-1} + \delta_2 Vol_{i,t-1} + \varepsilon_{i,t}$$

Where:

  * $r_{i,t}$: Log return of stock $i$ at time $t$.
  * $\alpha_i$: Unobserved firm-fixed effects.
  * $SentFirm$: Aggregated sentiment score for the firm.
  * $SentMacro$: Aggregated macro-sentiment score.

**Model Selection Criteria:**

1.  **F-Test:** Tests Fixed Effects vs. Pooled OLS.
2.  **Breusch-Pagan LM:** Tests Random Effects vs. Pooled OLS.
3.  **Hausman Test:** Tests Fixed Effects vs. Random Effects.

## 📝 Authors

  * **Project Lead:** Group 5 
  * **Tools Used:** Python, PyCharm, Jupyter Notebook.

-----

*Disclaimer: This project is for educational and research purposes. Financial data scraping must comply with the terms of service of the respective websites.*