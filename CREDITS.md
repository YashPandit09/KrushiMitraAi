# Credits

## Smart India Hackathon 2025

KrushiMitra AI grew out of our team's submission to **Smart India Hackathon (SIH) 2025** for problem statement
**SIH25044 - "AI-Powered Crop Yield Prediction and Optimization"**, set by the Government of Odisha under the
Agriculture, FoodTech & Rural Development theme.

The hackathon prototype - known during SIH as *KrushiBandhu AI* / *Yield-Ai* - lives at
[github.com/Shaunakrane914/Yield-Ai](https://github.com/Shaunakrane914/Yield-Ai).

**SIH 2025 team** (the idea, the problem framing and the first prototype):

- Shaunak Rane - [@Shaunakrane914](https://github.com/Shaunakrane914)
- Yash Pandit - [@YashPandit09](https://github.com/YashPandit09)
- and the rest of our SIH 2025 team

## This repository

This repository is a ground-up rebuild by Yash Pandit, made after the hackathon. It keeps the prototype's goal -
useful yield information for Odisha's farmers and planners - and replaces its placeholder inputs with official
district statistics, observed weather and cyclone tracks. It also adds out-of-sample evaluation, calibrated
uncertainty and a secure, deployable application. No code from the prototype is reused.

## Data

| Source | Used for | Licence / terms |
|---|---|---|
| Directorate of Economics & Statistics (DES) and UPAg crop statistics, via the [India Data Portal](https://indiadataportal.com) | District area, production and yield | Open Data Commons Attribution (ODC-By) |
| [NASA POWER](https://power.larc.nasa.gov) | Daily weather 1991 onwards | Free use with acknowledgement* |
| [NOAA IBTrACS v04r01](https://www.ncei.noaa.gov/products/international-best-track-archive) | Cyclone tracks | Public domain (US Government) |
| [geoBoundaries](https://www.geoboundaries.org) gbOpen IND ADM2 (2021) | District boundaries | ODbL 1.0 |
| [Open-Meteo](https://open-meteo.com) | Live 7-day forecast in the app | CC BY 4.0 |
| [Agmarknet via data.gov.in](https://data.gov.in) (optional) | Live mandi prices | Government Open Data License - India |

\* "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded through the NASA
Earth Science/Applied Science Program."

References:

- Kallenberg, M. et al. (2026). *CY-Bench: a comprehensive benchmark dataset for sub-national crop yield
  forecasting.* Earth System Science Data, 18, 3997. (Inspiration for the evaluation design.)
- Knapp, K. R. et al. (2010). *The International Best Track Archive for Climate Stewardship (IBTrACS).* BAMS 91, 363-376.
- Runfola, D. et al. (2020). *geoBoundaries: A global database of political administrative boundaries.* PLoS ONE 15(4).
- Zippenfenig, P. (2023). *Open-Meteo.com Weather API.* Zenodo. doi:10.5281/zenodo.7970649
