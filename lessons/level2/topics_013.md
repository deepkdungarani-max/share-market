# Depth 2 topics, part 13 of 20

Answer every topic below into `answers/answers_013.txt`: one `<topic id="N">…</topic>` block each, in the format of `lessons/README.md`.

## 2442 · Cross-currency and forward implied rate parity: USDINR option boxes vs onshore FX forwards and RBI swap windows
- Why: Analyzes parity trades in exchange-traded currency pairs where onshore capital controls create structural basis deviations.
- Under: Option pricing: Black-Scholes, binomial trees, put-call parity, implied volatility › Conversions, reversals and box spreads in Indian markets: costs, STT and margin

## 2443 · Derman's factor-of-two rule and local volatility calibration: why implied trees overstate skew dynamics
- Why: Explains why local volatility models systematically predict twice the skew slope for spot moves and how jump-diffusion fixes it.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Vanna, volga and charm: smile-consistent hedging and sticky-strike versus sticky-delta

## 2444 · The Vanna-Volga pricing and interpolation method: closed-form wings and exotic option valuation in FX and equity markets
- Why: Explores the exact analytical weighting equations and no-arbitrage boundary adjustments used by desks to price non-quoted strikes and barrier options.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Vanna, volga and charm: smile-consistent hedging and sticky-strike versus sticky-delta

## 2445 · Third-order Greeks: Speed, Zomma, Color and Ultima in extreme short-dated options risk
- Why: Investigates third-order sensitivities that become non-negligible in 0DTE options during expiry-afternoon gamma cascades.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Vanna, volga and charm: smile-consistent hedging and sticky-strike versus sticky-delta

## 2446 · Charm-driven intraday order flow and 0DTE dealer hedging: modeling the afternoon liquidity vortex
- Why: Analyzes how the mathematical divergence of Charm as T approaches zero forces algorithmic market makers into predictable futures order flow on expiry days.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Vanna, volga and charm: smile-consistent hedging and sticky-strike versus sticky-delta

## 2447 · Surface SVI (SSVI) and full arbitrage-free calibration algorithms across multiple maturities
- Why: Resolves slice-by-slice calendar arbitrage by ensuring full surface consistency across all maturities simultaneously
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Implied volatility surface modelling: SVI, SABR, local and stochastic volatility

## 2448 · Particle method and McKean-Vlasov McKean-type SDEs for non-parametric SLV calibration
- Why: Essential for calibrating the leverage function in Stochastic Local Volatility models without grid-based PDE instabilities
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Implied volatility surface modelling: SVI, SABR, local and stochastic volatility

## 2449 · Rough volatility models: fractional Brownian motion and Bergomi-Guyon power-law skew for short-dated options
- Why: Explains the steep power-law blowup of implied volatility skew for ultra-short (0-DTE) Indian index options
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Implied volatility surface modelling: SVI, SABR, local and stochastic volatility

## 2450 · Shifted SABR, Normal SABR, and Antonov's analytical approximations for low and zero-lower-bound underlying assets
- Why: Mandatory for interest rate options and commodities where underlying forward assets approach zero or negative territory
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Implied volatility surface modelling: SVI, SABR, local and stochastic volatility

## 2451 · Breeden-Litzenberger risk-neutral density reconstruction and fast Fourier transform (FFT) option pricing under Lévy jump-diffusion processes
- Why: Provides the mathematical machinery to extract model-free risk-neutral distributions directly from option quotes using spectral methods
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Implied volatility surface modelling: SVI, SABR, local and stochastic volatility

## 2452 · Cross-gamma and correlation stress testing in multi-asset equity and index option books
- Why: Explores how nonlinear cross-asset correlations break down during systemic market shocks, expanding cross-gamma and basket margin deficits.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Option portfolio risk: stress grids, SPAN scenarios and Greeks-based limits

## 2453 · Principal component decomposition of implied volatility surfaces for bucketed vega limit design
- Why: Examines how quantitative desks model extreme shifts, twists, and butterfly curvature in implied volatility using principal components.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Option portfolio risk: stress grids, SPAN scenarios and Greeks-based limits

## 2454 · Clearinghouse SPAN 2 and filtered historical simulation VaR margining architectures
- Why: Analyzes the transition from static 16-scenario SPAN grids to historical simulation Value-at-Risk portfolio margining in modern clearinghouses.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Option portfolio risk: stress grids, SPAN scenarios and Greeks-based limits

## 2455 · Algorithmic gamma band hedging and optimal execution under non-zero transaction costs
- Why: Focuses on algorithmic execution algorithms that automatically rehedge Delta and Gamma Cash boundaries while minimizing market impact and adverse selection.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Option portfolio risk: stress grids, SPAN scenarios and Greeks-based limits

## 2456 · Jump-diffusion and discrete barrier modeling for single-stock derivatives risk management
- Why: Investigates quantitative jump-diffusion models for pricing and stress testing earnings gap risks and dividend drop surprises in single-stock books.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Option portfolio risk: stress grids, SPAN scenarios and Greeks-based limits

## 2667 · Whalley-Wilmott asymptotic hedging bands and utility-based stochastic control
- Why: Explores Hamilton-Jacobi-Bellman PDEs, state-dependent no-transaction bands, and asymptotic expansions under utility maximization.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Discrete delta hedging: transaction costs, Leland adjustment and hedging error

## 2668 · Boyle-Emanuel distribution of discrete hedging errors: skewness, kurtosis, and jump risk
- Why: Analyzes higher moments, fat-tailed jump diffusions, and skewness of tracking errors when continuous diffusion assumptions fail.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Discrete delta hedging: transaction costs, Leland adjustment and hedging error

## 2669 · Super-replication and the Soner-Shreve-Cvitanić triviality theorem under continuous transaction costs
- Why: Examines the mathematical proof that continuous super-replication under proportional transaction costs degenerates to buy-and-hold.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Discrete delta hedging: transaction costs, Leland adjustment and hedging error

## 2670 · Microstructure friction in delta hedging: market impact models and order book execution algos
- Why: Focuses on market impact, limit order book queues, and optimal execution algorithms (Almgren-Chriss) for dynamic delta rebalancing.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Discrete delta hedging: transaction costs, Leland adjustment and hedging error

## 2671 · Physical settlement delivery margins, SLBM borrow costs, and stock option expiration pin risk
- Why: Covers delivery margins, SLBM borrow logistics, and expiry-day unwinding protocols for high-gamma Indian stock options.
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › Discrete delta hedging: transaction costs, Leland adjustment and hedging error

## 2672 · Internal Architecture of SPAN Risk Parameter Files and Real-Time Grid Parsing Algorithms
- Why: Explores the algorithmic file structures (.spn, .pa2) and exact numerical valuation routines used by clearinghouse risk engines to revalue portfolios intraday
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › SPAN margin mechanics for short options and expiry-day ELM

## 2673 · Physical Settlement Failure Mechanics and Auction Clearing Defaults in Stock Derivatives
- Why: Examines how exchange circuit breakers, price bands, and auction mechanisms alter physical delivery margin liabilities during catastrophic tail events
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › SPAN margin mechanics for short options and expiry-day ELM

## 2674 · Cross-Margining Mechanics Between Cash Market Portfolios and Index Derivative Contracts
- Why: Analyzes cross-margining optimization between cash index ETF holdings and equity index derivatives under clearinghouse netting agreements
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › SPAN margin mechanics for short options and expiry-day ELM

## 2675 · Market-Maker Inventory Gamma Dynamics Under Rationalized Single-Benchmark Expiry Regimes
- Why: Addresses how the removal of weekly expiries concentrates market-maker gamma and changes intraday volatility smile dynamics on monthly expiries
- Under: Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice › SPAN margin mechanics for short options and expiry-day ELM

## 2676 · Global Arbitrage-Free SSVI Surfaces and Jacquier-Gatheral Curvature Bounds
- Why: To build continuous-time pricing engines that eliminate SVI slice-crossing arbitrage across the entire term structure natively
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Volatility surface construction: delta-space quoting, risk reversals, butterflies, SVI and SABR fits

## 2677 · Analytical Dupire Local Volatility Extraction and Density Inversion from SVI
- Why: To extract the continuous risk-neutral probability density and local volatility directly from calibrated SVI parameters without numerical noise
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Volatility surface construction: delta-space quoting, risk reversals, butterflies, SVI and SABR fits

## 2678 · Arbitrage-Free SABR PDE Formulations and Tail Extrapolations
- Why: To price extreme tail options where Hagan's asymptotic formula breaks down into negative probabilities or complex numbers
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Volatility surface construction: delta-space quoting, risk reversals, butterflies, SVI and SABR fits

## 2679 · FX Smile Construction via Vanna-Volga and Premium-Adjusted Delta Conventions
- Why: To construct delta-space volatility surfaces for emerging market currency options subject to RBI dual-currency intervention bounds
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Volatility surface construction: delta-space quoting, risk reversals, butterflies, SVI and SABR fits

## 2680 · Gamma swaps, entropy contracts and corridor variance swaps: Payoff profiles and jump-robust volatility trading
- Why: Explores alternative contract specifications that eliminate the jump shortfall error inherent in standard 1/K^2 log contract replication
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Variance swaps, log contract replication and the variance risk premium in Nifty

## 2681 · Index dispersion trading on Nifty 50: Replicating single-stock vs index variance and harvesting the correlation risk premium
- Why: Analyzes how desks trade the wedge between Nifty 50 index variance and single-stock constituent variances to harvest the correlation risk premium
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Variance swaps, log contract replication and the variance risk premium in Nifty

## 2682 · High-frequency realized volatility estimators for Indian equities: Realized kernels, bipower variation and jump extraction in tick data
- Why: Essential for measuring true high-frequency continuous quadratic variation versus discrete jump components from NSE tick-by-tick order book data
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Variance swaps, log contract replication and the variance risk premium in Nifty

## 2683 · CBOE SKEW, risk-neutral higher moments and the cubic contract replication in Indian index derivatives
- Why: Extends the Carr-Madan spanning methodology to higher moments to quantify skewness and kurtosis risk premia in Indian index derivatives
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Variance swaps, log contract replication and the variance risk premium in Nifty

## 2684 · Realized Kernel and Pre-Averaging Estimators for Tick-Level Microstructure Noise on NSE
- Why: Resolves high-frequency bid-ask bounce and asynchronous trade arrival when sampling at sub-1-minute intervals on NSE equity and derivative feeds
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › GARCH, EWMA and HAR-RV volatility forecasting with Indian index data

## 2685 · Intraday Diurnal Seasonality Modeling and Deseasonalized High-Frequency Volatility
- Why: Filters the predictable intraday U-shaped volume and volatility pattern across the NSE trading session (09:15 open surge, 12:30 lull, 15:00 MOC push) before RV estimation
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › GARCH, EWMA and HAR-RV volatility forecasting with Indian index data

## 2686 · Multivariate GARCH (DCC-GARCH and Copula-GARCH) for Dynamic Cross-Hedging on NSE
- Why: Essential for multi-asset equity/derivative desks hedging sector baskets against Nifty using time-varying conditional correlations
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › GARCH, EWMA and HAR-RV volatility forecasting with Indian index data

## 2687 · Jump-Robust Realized Estimators (MinRV and MedRV) in Intraday Jump Regimes
- Why: Extends jump-diffusion theory to robust estimators (MinRV, MedRV) less sensitive to consecutive zero returns and market halts than Bipower Variation
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › GARCH, EWMA and HAR-RV volatility forecasting with Indian index data

## 2688 · GARCH-in-Mean (GARCH-M) Modeling and the Time-Varying Equity Risk Premium in India
- Why: Quantifies whether expected stock index excess returns are statistically driven by conditional variance over time in emerging markets
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › GARCH, EWMA and HAR-RV volatility forecasting with Indian index data

## 2689 · Jump-diffusion calibration for discrete event risk: Merton and Kou models on Indian equity derivatives
- Why: Understand how non-Gaussian jump distributions and finite Poisson arrivals replace BSM to price discontinuous Indian earnings gaps
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Event volatility and IV crush: budget, results and election-day term structure kinks

## 2690 · Cross-expiry margin optimization and basis risk modeling under SEBI's decoupled expiry-day margin rules
- Why: Address the breakdown of calendar spreads caused by SEBI's mandate revoking calendar margin relief on expiry day
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Event volatility and IV crush: budget, results and election-day term structure kinks

## 2691 · Vanna-Volga pricing and dynamic hedging of deep OTM crash puts under political regime shifts
- Why: Examine how institutional dealers price and hedge the severe crash-put skew that emerges prior to national election counting days
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Event volatility and IV crush: budget, results and election-day term structure kinks

## 2692 · Physical delivery assignment dynamics and squeeze mechanics during quarterly earnings expiry weeks
- Why: Analyze how high post-event IV crush interacts with physical share settlement to create market anomalies in single-stock F&O
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › Event volatility and IV crush: budget, results and election-day term structure kinks

## 2693 · Anti-procyclical margin buffering and liquidity impact under CPMI-IOSCO Principle 5
- Why: Understand the systemic impact and regulatory methods designed to prevent CCP margin spikes from causing market fire sales
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › How SPAN scenarios, VaR and ELM margins respond to volatility regimes

## 2694 · Cross-margining mechanics and basis risk between cash baskets and index futures
- Why: Examine how correlation breakdown during crashes impacts margin credits between index derivatives and constituent equities
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › How SPAN scenarios, VaR and ELM margins respond to volatility regimes

## 2695 · Algorithmic portfolio replication of the NCL SPAN 16-scenario grid for real-time risk engines
- Why: Learn to build high-frequency C++ pre-trade margin check engines that replicate NCL SPAN 16-scenario arrays
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › How SPAN scenarios, VaR and ELM margins respond to volatility regimes

## 2696 · Staggered delivery margin dynamics and physical settlement failure risk in equity derivatives
- Why: Master the multi-day liquidity demands of physical settlement in expiring single-stock options and futures
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › How SPAN scenarios, VaR and ELM margins respond to volatility regimes

## 2697 · Intraday peak margin sampling theory: Poisson arrival modeling and optimal intraday collateral buffering
- Why: Optimize intra-day capital allocation against randomized exchange margin snapshot intervals
- Under: Volatility: historical vs implied, India VIX, volatility smile and skew, term structure › How SPAN scenarios, VaR and ELM margins respond to volatility regimes

## 2698 · Algorithmic execution models (Almgren-Chriss, Kyle's Lambda) and order-book depth dynamics in Indian cash equities
- Why: Explores the mathematical and algorithmic infrastructure of market impact models and how quantitative desks detect or execute high-frequency order book sweeps.
- Under: Option strategies: spreads, straddles, strangles, iron condors, calendars, ratio spreads, hedging › Expiry-day gamma, pin risk and index-manipulation case studies (Jane Street / SEBI 2025)

## 2699 · Comparative global settlement architectures: SPX AM/PM settlement vs. European physical assignment vs. Indian hybrid frameworks
- Why: Deepens understanding of the structural differences between US cash-settled SPX/NDX options, European equity options, and Indian mandatory physical delivery.
- Under: Option strategies: spreads, straddles, strangles, iron condors, calendars, ratio spreads, hedging › Expiry-day gamma, pin risk and index-manipulation case studies (Jane Street / SEBI 2025)

## 2700 · The asymptotic geometry of the volatility smile: Jump-diffusion and local volatility breakdowns in 0DTE options
- Why: Examines the statistical physics and quantitative modeling of implied volatility surfaces as tau approaches zero, including implied distribution bimodality.
- Under: Option strategies: spreads, straddles, strangles, iron condors, calendars, ratio spreads, hedging › Expiry-day gamma, pin risk and index-manipulation case studies (Jane Street / SEBI 2025)

## 2701 · Forensic econometrics in securities litigation: Reconstructing manipulative intent from cross-product high-frequency order logs under SEBI PFUTP regulations
- Why: Covers the legal precedents, statistical forensics, and econometrics SEBI uses under PFUTP regulations to prove market manipulation versus legitimate market making.
- Under: Option strategies: spreads, straddles, strangles, iron condors, calendars, ratio spreads, hedging › Expiry-day gamma, pin risk and index-manipulation case studies (Jane Street / SEBI 2025)
