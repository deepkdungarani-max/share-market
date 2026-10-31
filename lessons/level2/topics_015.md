# Depth 2 topics, part 15 of 20

Answer every topic below into `answers/answers_015.txt`: one `<topic id="N">…</topic>` block each, in the format of `lessons/README.md`.

## 2836 · Regime-Switching Risk Parity: Dynamic Covariance Estimation via Hidden Markov Models
- Why: Understand how to dynamically alter asset allocation when the equity-bond correlation breaks down during stagflation
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Volatility targeting and risk-parity position sizing

## 2837 · Tail Risk Parity: Equal Expected Shortfall and Downside Semi-Variance Allocation
- Why: Overcome Gaussian distribution assumptions by equalizing tail risk and Conditional Value at Risk in emerging markets
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Volatility targeting and risk-parity position sizing

## 2838 · Discrete Lot Size and Market Impact-Constrained Quant Portfolio Construction
- Why: Incorporate SEBI contract lot sizes and Almgren-Chriss market impact directly into the risk-parity optimization engine
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Volatility targeting and risk-parity position sizing

## 2839 · Extreme Value Theory (EVT) and Peaks-Over-Threshold (POT) modeling for Indian market tail risk
- Why: Models extreme non-normal fat tails parametrically beyond empirical data boundaries
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Value at Risk, expected shortfall and stress testing in Indian portfolios

## 2840 · Quantitative backtesting of VaR and Expected Shortfall: Christoffersen independence tests and joint elicitability
- Why: Crucial for clearing regulatory audits and validating model stability under BCBS/SEBI standards
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Value at Risk, expected shortfall and stress testing in Indian portfolios

## 2841 · Liquidity-Adjusted VaR (L-VaR) and endogenous market impact modeling using the Almgren-Chriss framework
- Why: Essential for institutional block execution and illiquid small-cap positioning without price crashes
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Value at Risk, expected shortfall and stress testing in Indian portfolios

## 2842 · Rockafellar-Uryasev CVaR optimization and linear programming for institutional portfolio construction
- Why: Modern computational method replacing Markowitz mean-variance optimization with linear programming
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Value at Risk, expected shortfall and stress testing in Indian portfolios

## 2843 · Fundamental Review of the Trading Book (FRTB): Internal Models Approach, non-modellable risk factors (NMRFs), and multi-horizon Expected Shortfall
- Why: The international regulatory benchmark replacing VaR across tier-1 investment bank trading desks
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Value at Risk, expected shortfall and stress testing in Indian portfolios

## 2844 · Block Bootstrap and Stationary Bootstrap for Autocorrelated Time Series in Algorithmic Trading
- Why: Essential for modeling regime clustering and persistent losing streaks that standard IID Monte Carlo fails to capture.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Monte Carlo simulation of trade sequences and drawdown distributions

## 2845 · Conditional Drawdown at Risk (CDaR) Optimization for Dynamic Capital Allocation
- Why: Solves portfolio asset weights directly to minimize the tail drawdown distribution rather than traditional mean-variance volatility.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Monte Carlo simulation of trade sequences and drawdown distributions

## 2846 · Lundberg-Cramér Ruin Theory and Asymptotic Barrier Crossing in Leveraged Derivatives Portfolios
- Why: Provides rigorous continuous-time analytical boundaries for ruin probabilities when trade jump sizes follow heavy-tailed distributions.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Monte Carlo simulation of trade sequences and drawdown distributions

## 2847 · Maximum Adverse Excursion (MAE) and Intraday Path Simulation for Peak Margin Compliance
- Why: Extends trade-level Monte Carlo to high-frequency intraday price paths to prevent broker RMS forced liquidations under peak margin rules.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Monte Carlo simulation of trade sequences and drawdown distributions

## 2848 · Regime-Switching Monte Carlo Using Hidden Markov Models (HMM) for Strategy Stress Testing
- Why: Simulates realistic transitions between low-volatility trending and high-volatility sideways regimes in equity indices.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Monte Carlo simulation of trade sequences and drawdown distributions

## 2849 · Algorithmic SPAN Replication and Real-Time Margin Forecasting in C++ and Python
- Why: Essential for high-frequency option market makers to forecast exchange margin updates and avoid broker auto-liquidations before official files drop.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Margin stress and tail-risk management for option writers (SPAN, ELM, expiry-day rules)

## 2850 · Securities Lending and Borrowing Mechanism (SLBM) and Physical Delivery Shortage Arbitrage
- Why: Crucial for managing single-stock short call assignment risks, borrowing shares, and avoiding punitive 20% exchange auction default penalties.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Margin stress and tail-risk management for option writers (SPAN, ELM, expiry-day rules)

## 2851 · Intraday Gamma Scalping and Dynamic Delta Hedging Under Indian STT and Friction Drag
- Why: Teaches option writers how to mathematically neutralize catastrophic gamma stress on expiry day while managing non-linear transaction costs and Securities Transaction Tax (STT).
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Margin stress and tail-risk management for option writers (SPAN, ELM, expiry-day rules)

## 2852 · CCP Default Waterfalls, Clearing Member Capital Buffers, and Systemic Risk Resolution in Indian Derivatives
- Why: Explains the institutional capital defense layers, waterfall allocations, and Core Settlement Guarantee Fund recovery if major clearing members default.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Margin stress and tail-risk management for option writers (SPAN, ELM, expiry-day rules)

## 2853 · Volatility Surface Skew Dynamics and Kurtosis Jump-Diffusion Modeling in Index Options
- Why: Provides the quantitative pricing framework needed to identify mispriced tail risk across option strikes before SPAN volatility shocks materialize.
- Under: Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin › Margin stress and tail-risk management for option writers (SPAN, ELM, expiry-day rules)

## 2896 · Cross-Sectional vs. Time-Series (Trend-Following) Momentum in Indian Equities and Derivatives
- Why: Examines the operational and statistical divergence between trend-following (time-series) and long-only cross-sectional momentum in Indian F&O equities.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Factor investing in India: value, momentum, quality, low volatility, size, with Nifty factor index construction and cyclicality

## 2897 · Factor Crowding, Liquidity Decay, and Capacity Constraints in Indian Mid- and Small-Cap Factor Portfolios
- Why: Explores the market impact limits, circuit filter constraints (5/10/20%), and liquidity decay when scaling smart-beta strategies into Indian mid- and small-caps.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Factor investing in India: value, momentum, quality, low volatility, size, with Nifty factor index construction and cyclicality

## 2898 · Sector-Neutral vs. Broad Cross-Sectional Factor Screening: Disentangling True Factor Alpha from Macro Industry Bets
- Why: Analyzes how unconstrained factor screens accidentally take massive macroeconomic sector bets and how to construct Barra-style sector-neutral factor portfolios.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Factor investing in India: value, momentum, quality, low volatility, size, with Nifty factor index construction and cyclicality

## 2899 · Machine Learning and Regime-Switching Architectures for Dynamic Factor Allocation in India
- Why: Covers quantitative techniques (Hidden Markov Models, Macro Ensembles) to systematically rotate between factors across Indian credit and business cycles.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Factor investing in India: value, momentum, quality, low volatility, size, with Nifty factor index construction and cyclicality

## 2900 · Meucci’s Fully Flexible Views and Entropy Pooling
- Why: Extends Black–Litterman beyond normal distributions to handle extreme skewness, kurtosis, and macro tail-risk scenarios in Indian equities.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Black–Litterman, shrinkage covariance estimation and robust portfolio optimisation

## 2901 · Random Matrix Theory, Marchenko–Pastur Law, and Spectral Covariance Cleaning
- Why: Provides the mathematical machinery of Random Matrix Theory to filter noise eigenvalues from correlation matrices before shrinkage.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Black–Litterman, shrinkage covariance estimation and robust portfolio optimisation

## 2902 · Second-Order Cone Programming (SOCP) and Semidefinite Programming (SDP) in Portfolio Selection
- Why: Details how robust portfolio constraints are formulated and solved numerically using modern interior-point algorithms.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Black–Litterman, shrinkage covariance estimation and robust portfolio optimisation

## 2903 · Michaud Resampled Efficiency and Bootstrapped Frontier Mechanics
- Why: Explores the simulation-based bootstrap resampling alternative to analytical robust optimization invented by Richard Michaud.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Black–Litterman, shrinkage covariance estimation and robust portfolio optimisation

## 2904 · Transaction Cost, STT, and Capital Gains Tax-Aware Portfolio Optimization
- Why: Analyzes after-tax mean-variance frontiers, lot accounting (FIFO vs specific ID), and turnover regularization under Indian tax law.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Black–Litterman, shrinkage covariance estimation and robust portfolio optimisation

## 2905 · Hierarchical Risk Parity (HRP) and Dendrogram Clustering in Portfolio Allocation
- Why: Explores machine learning tree clustering to allocate risk weights without inverting the covariance matrix, avoiding Markowitz instability.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Risk parity, minimum variance and volatility targeting portfolios

## 2906 · Cyclical Coordinate Descent (CCD) and Newton-Raphson Numerical Solvers for Large-Scale Risk Budgeting
- Why: Essential for large institutional portfolios to solve convex risk parity optimization across thousands of stocks with extreme speed.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Risk parity, minimum variance and volatility targeting portfolios

## 2907 · Constant Proportion Portfolio Insurance (CPPI) and Dynamic Risk Floor Engineering
- Why: Provides capital guarantee floors while dynamically scaling equity participation, widely used in structured PMS and insurance products.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Risk parity, minimum variance and volatility targeting portfolios

## 2908 · Commodity and Trend-Following Overlays for Multi-Asset Risk Parity
- Why: Crucial for designing macro-weatherproof portfolios that maintain risk parity during supply-shock inflation and stagflation regimes.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Risk parity, minimum variance and volatility targeting portfolios

## 2909 · Realized Intraday Volatility Estimators and Jump-Diffusion Modeling for Algorithmic Vol Targeting
- Why: Enables algorithmic execution desks to dynamically adjust intraday volatility targets using high-frequency tick data.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Risk parity, minimum variance and volatility targeting portfolios

## 2910 · Copula-Based Tail Dependence and Non-Linear Portfolio Risk Modeling
- Why: Models tail dependence and asymmetric crash co-movements that linear correlation matrices miss
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Value at Risk, expected shortfall and stress testing for Indian portfolios

## 2911 · Filtered Historical Simulation (FHS) and GARCH-EVT Frameworks for Intraday Risk
- Why: Enables real-time intraday risk forecasting by scaling empirical residuals with conditional heteroskedasticity
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Value at Risk, expected shortfall and stress testing for Indian portfolios

## 2912 · Algorithmic Liquidity-Adjusted VaR (L-VaR) and Endogenous Market Impact Modeling
- Why: Prevents catastrophic liquidity traps during portfolio liquidation in illiquid and circuit-prone stocks
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Value at Risk, expected shortfall and stress testing for Indian portfolios

## 2913 · Reverse Stress Testing and Macroeconomic Shock Simulation for Indian Banking Portfolios
- Why: Critical for designing macro-prudential survival plans across multi-asset banking trading books
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Value at Risk, expected shortfall and stress testing for Indian portfolios

## 2914 · SPAN Margin Mechanics and Multi-Asset Cross-Margining across Indian Exchanges
- Why: Explores the 16-scenario grid engine used by Indian clearing corporations to margin complex derivatives
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Value at Risk, expected shortfall and stress testing for Indian portfolios

## 2915 · Multiple testing corrections, False Discovery Rate (FDR) and machine learning methods for factor discovery
- Why: Explores the econometric tools required to weed out false anomalies and evaluate multiple hypothesis testing in large-scale factor libraries.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Arbitrage Pricing Theory, the Fama–French five-factor model and the factor zoo debate

## 2916 · The q-factor model and investment-based asset pricing
- Why: Examines the supply-side, investment-based alternative to Fama–French that models asset pricing from firm first-order optimization conditions.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Arbitrage Pricing Theory, the Fama–French five-factor model and the factor zoo debate

## 2917 · Gibbons–Ross–Shanken (GRS) test and Generalized Method of Moments (GMM) estimation of factor models
- Why: Covers the core econometric framework used to test whether multi-factor models span the mean-variance frontier under non-normal residuals.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Arbitrage Pricing Theory, the Fama–French five-factor model and the factor zoo debate

## 2918 · Microstructure frictions, liquidity constraints, and capacity limits in Indian factor portfolios
- Why: Analyzes real-world portfolio implementation constraints, including circuit filters, borrow availability, and turnover impact on Indian factor returns.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Arbitrage Pricing Theory, the Fama–French five-factor model and the factor zoo debate

## 2919 · The characteristics versus covariances debate: Daniel–Titman methodology and behavioral foundations
- Why: Investigates whether equity return premiums represent compensation for systematic macroeconomic risk or behavioral mispricing of firm characteristics.
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Arbitrage Pricing Theory, the Fama–French five-factor model and the factor zoo debate

## 2920 · Fowler–Rorke and Scholes–Williams estimators: mathematical derivation, auto-covariance corrections, and empirical efficiency in thin markets
- Why: Derives full asymptotic covariance matrices and optimal weighting schemes when benchmark returns exhibit high-order serial correlation in emerging markets
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Estimating beta and alpha in practice: regression windows, Dimson adjustment, Blume adjustment and benchmark choice

## 2921 · Time-varying beta estimation: Kalman filter state-space models and GARCH-based conditional CAPM
- Why: Replaces static rolling regression windows with dynamic state-space models to track real-time structural shifts in systematic risk
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Estimating beta and alpha in practice: regression windows, Dimson adjustment, Blume adjustment and benchmark choice

## 2922 · High-frequency beta estimation: realized beta, intraday microstructure noise, and jump-robust estimators
- Why: Addresses ultra-high-frequency algorithmic trading data where market microstructure noise, bid-ask bounce, and discrete jumps distort covariance estimation
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Estimating beta and alpha in practice: regression windows, Dimson adjustment, Blume adjustment and benchmark choice

## 2923 · Cross-sectional Bayesian hierarchical models for sector and industry beta shrinkage
- Why: Extends univariate Vasicek shrinkage to multi-level Bayesian hierarchies incorporating sector, industry, and capitalization peer groups
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Estimating beta and alpha in practice: regression windows, Dimson adjustment, Blume adjustment and benchmark choice

## 2924 · Performance attribution under benchmark mismatch: Brinson-Fachler vs multi-index risk-adjusted decomposition
- Why: Disentangles pure stock-selection skill from broad market, sector allocation, and capitalization tilts when benchmarks are imperfect
- Under: Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models › Estimating beta and alpha in practice: regression windows, Dimson adjustment, Blume adjustment and benchmark choice

## 2967 · Combinatorial Purged Cross-Validation (CPCV) with Overlapping Event Labels and Information Leakage Bounds
- Why: Resolves information leakage and auto-correlation in CSCV for path-dependent option and equity intraday positions
- Under: Quantitative trading: backtesting, walk-forward, overfitting, look-ahead bias, transaction costs › Deflated Sharpe Ratio and Probability of Backtest Overfitting: derivation and Python implementation

## 2968 · False Discovery Rate (FDR) and Benjamini-Hochberg-Yekutieli Corrections in Multi-Asset Cross-Sectional Factor Mining
- Why: Provides rigorous multiple-testing control across high-dimensional factor sweeps without extreme Gumbel over-deflation
- Under: Quantitative trading: backtesting, walk-forward, overfitting, look-ahead bias, transaction costs › Deflated Sharpe Ratio and Probability of Backtest Overfitting: derivation and Python implementation

## 2969 · Stochastic Dominance and Non-Parametric Rank Inversion in Algorithmic Strategy Selection
- Why: Determines whether an out-of-sample strategy performance distribution is fundamentally superior or merely higher in mean
- Under: Quantitative trading: backtesting, walk-forward, overfitting, look-ahead bias, transaction costs › Deflated Sharpe Ratio and Probability of Backtest Overfitting: derivation and Python implementation
