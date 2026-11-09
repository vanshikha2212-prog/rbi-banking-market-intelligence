# Data sources, conventions and verification

## What the corrected dataset contains

The frozen study covers 18 RBI policy announcements in 2023–2025 and daily market observations from 1 January 2021 through 31 December 2025. It uses six banks, Nifty 50 as the primary market benchmark, and Nifty Bank as a sensitivity benchmark.

The corrected snapshot contains 1,236 common observed trading dates and 9,888 asset-date price rows. The six banks contribute 7,416 price rows and 7,410 usable daily returns; the first observation for each bank has no prior price. These counts distinguish prices from returns. They also distinguish thousands of daily market observations from the 18 policy announcements that determine the effective event-study sample.

Yahoo Finance is the actual provider of the main market history. NSE official archives supply one missing benchmark observation and independent checks of selected bank and index prices. This project does not claim that the complete history was acquired from, or exhaustively reconciled against, NSE.

## Market acquisition and preserved evidence

The new acquisition code uses Python's standard-library HTTPS client to request the public Yahoo Finance chart endpoint. It does not require or claim to execute `yfinance`. An explicit refresh requests each of these eight symbols separately:

| Symbol | Security | Classification |
|---|---|---|
| HDFCBANK.NS | HDFC Bank | Private bank |
| ICICIBANK.NS | ICICI Bank | Private bank |
| AXISBANK.NS | Axis Bank | Private bank |
| SBIN.NS | State Bank of India | Public bank |
| BANKBARODA.NS | Bank of Baroda | Public bank |
| CANBK.NS | Canara Bank | Public bank |
| ^NSEI | Nifty 50 | Price-index benchmark |
| ^NSEBANK | Nifty Bank | Price-index benchmark |

Endpoint: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}`.

The query specifies daily observations, `period1=1609459200`, `period2=1767225600`, `events=div,splits`, and `includeAdjustedClose=true`. The start is inclusive and the end is exclusive. Unix timestamps are converted to the exchange's `Asia/Kolkata` calendar before extracting the date. The response metadata must identify the requested symbol, INR, and the expected Indian exchange timezone.

The acquisition timestamps in the original corrected snapshot are 2 November 2026 UTC. Exact timestamps for each request are recorded in `data/raw/yahoo_retrieval_records.json`; this file, not a manually typed date in a report, is the authoritative retrieval record. A later explicit refresh changes the source bytes and hashes and requires regenerating every downstream result.

| Evidence | Location | Purpose |
|---|---|---|
| Original Yahoo responses | `data/raw/yahoo_chart_2021_2025/*.json` | Unmodified provider-returned bytes, prices, actions and metadata |
| Query and response records | `data/raw/yahoo_retrieval_records.json` | URL, retrieval timestamp, status, byte size and SHA-256 per asset |
| Normalized Yahoo quotes | `data/raw/market_prices_2021_2025.csv` | Tidy representation before the documented NSE repair; this is generated from the JSON, not an original vendor CSV |
| Original NSE index archive | `data/raw/nse_index_close_2025-02-01.csv` | Exact official observation for the missing Budget-session benchmark row |
| NSE equity archives and checks | `data/raw/nse_spot_checks/` | Original ZIPs, extracted bhavcopies, retrieval metadata, and 12 bank-close comparisons |
| Repair ledger | `data/raw/market_repairs.json` | Exact before/after values, reason, source and source hash |
| Corporate-action table | `data/raw/corporate_actions_2021_2025.csv` | 28 dividend records and two split/bonus-ratio records returned by the provider |
| Data diagnostics | `data/raw/market_diagnostics.json` | Split-date returns, large movements, event-window dividend overlaps, and independent price checks |
| Reproducibility manifest | `data/raw/market_manifest.json` | Input/output hashes, query settings, versions, coverage, counts and limitations |
| Validated analytical panel | `data/processed/market_panel.csv` | Complete synchronized prices, source flags, price returns and adjusted-price sensitivity returns |

A checksum identifies the bytes used. It does not prove that every observation is economically correct. The source snapshots make the checked version reproducible even when a provider later revises its historical data or changes its endpoint.

## Primary returns and adjustment policy

The primary outcome uses simple **price returns** from Yahoo's vendor-returned split-adjusted `Close`:

\[
R_{i,t}=P_{i,t}/P_{i,t-1}-1.
\]

Yahoo's historical-price page distinguishes split-adjusted Close from Adjusted Close, which also incorporates dividend/distribution adjustments. See the provider's [historical-price column definitions](https://finance.yahoo.com/quote/%5EGSPC/history/?p=%5Egspc). The selected bank observations were additionally reconciled to contemporaneous NSE prices using the recorded subsequent split ratios, rather than assuming that an unadjusted exchange price and a retrospectively adjusted Yahoo price should have equal numerical levels.

This price-return convention matches the use of Nifty price indices as benchmarks. Cash dividends are not included in the primary shareholder return. An ex-dividend price drop can therefore appear in price returns even though a shareholder also receives cash. Such a drop is not automatically a data error, and it should not automatically be attributed to RBI news.

The panel retains `adj_close` and computes `adj_return` for a separate, explicitly labelled dividend-adjustment sensitivity. Bank adjusted-price returns against these Nifty price indices do not form a fully matched total-return specification. A future total-return study should acquire suitable total-return benchmarks and specify the same dividend convention on both sides. The current project does not label its adjusted-bank-return sensitivity as a fully matched total-return market model.

No prices are interpolated or forward-filled. Both return calculations explicitly use `pct_change(fill_method=None)`. A missing session is never silently compressed into a return labelled as an ordinary one-session return. Large observed movements are flagged and retained instead of being automatically winsorized away.

## One source-backed repair: 1 February 2025

Yahoo returned timestamps for the Saturday Budget trading session on 1 February 2025 but null OHLC, adjusted close and volume for Nifty Bank. The other seven study assets had valid observations on that date. Treating the null row as a holiday or filling its price from the previous day would create incorrect return alignment around the February policy announcement.

The missing row is replaced with the exact Nifty Bank observation in the [NSE daily index archive for 1 February 2025](https://archives.nseindia.com/content/indices/ind_close_all_01022025.csv):

| Field | Official observation |
|---|---:|
| Open | 49,592.55 |
| High | 50,009.50 |
| Low | 48,925.45 |
| Close | 49,506.95 |
| Volume | 118,009,351 |

Because this is a price index, the repaired adjusted-close field is set equal to its closing level. Original Yahoo JSON and the pre-repair normalized CSV remain unchanged. The analytical row records its NSE source, and the repair ledger records every replaced field. The NSE archive is retained with retrieval metadata and its SHA-256.

The same archive provides a small independent Nifty 50 check: Yahoo Close is 23,482.150390625 versus the official 23,482.15, a difference of approximately 0.000391 index points. This is within the documented 0.02-point tolerance. It is one checked index observation, not a whole-history accuracy rate.

## Independent bank-price checks

Two additional NSE equity archives were retained:

1. [9 August 2023 cash-market bhavcopy](https://archives.nseindia.com/content/historical/EQUITIES/2023/AUG/cm09AUG2023bhav.csv.zip), a date that overlaps ICICI Bank's dividend and the August 2023 policy window.
2. [6 June 2025 UDiFF cash-market bhavcopy](https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250606_F_0000.csv.zip), the RBI rate-cut date that also contains Bank of Baroda's ex-dividend observation.

All six bank closes were checked on both dates. NSE's contemporaneous price is divided by any subsequent provider-reported split ratio before comparison with Yahoo's restated Close. For example, Canara Bank's 9 August 2023 NSE close of ₹336.10 becomes ₹67.22 after its subsequent 5:1 split; HDFC Bank's 9 August 2023 NSE close of ₹1,650.50 becomes ₹825.25 after its subsequent 2:1 share-ratio event.

All 12 selected bank-close comparisons pass a ₹0.02 tolerance. The maximum absolute difference in this snapshot is approximately ₹0.000049, consistent with the precision of the vendor's floating-point price representation. The pipeline verifies the retained ZIP hashes, checks that extracted CSV bytes match the archive members, regenerates the comparison table, and fails if a comparison exceeds the tolerance. This provides concrete evidence for selected dates and the adjustment convention. It does not justify calling every historical price independently verified.

## Corporate actions and event interpretation

The vendor returns two share-ratio events within the study's market window:

| Date | Bank | Vendor share ratio | Price return on that date |
|---|---|---:|---:|
| 15 May 2024 | Canara Bank | 5:1 | Approximately +5.02% |
| 26 August 2025 | HDFC Bank | 2:1 | Approximately −0.88% |

The absence of mechanical −80% or −50% drops, together with the selected NSE comparisons, supports the interpretation of the retained Close series as split-adjusted. This is a diagnostic, not an exhaustive verification of every historical corporate action.

The provider also returns 28 dividend records. Two overlap the primary `[-1,+1]` event windows:

| Policy event | Bank | Ex-dividend date | Relative trading day | Vendor dividend amount |
|---|---|---|---:|---:|
| 10 August 2023 | ICICI Bank | 9 August 2023 | −1 | ₹8.00 |
| 6 June 2025 | Bank of Baroda | 6 June 2025 | 0 | ₹8.35 |

Seven bank-event dividend overlaps occur in the widest `[-5,+5]` windows. The complete list, with relative trading-day positions, is generated in the diagnostics JSON. Dividend amounts are retained on the vendor's stated share basis; they should not be mechanically mixed with pre-split exchange prices without checking the basis.

The analysis should present the primary price-return result alongside an exclusion of dividend-overlapping bank-event observations and the labelled adjusted-bank-return sensitivity. An exclusion changes the sample composition, so it is a sensitivity check rather than a replacement hidden inside the primary result.

## RBI event sources and date correction

The policy event is the date the decision became public, not the meeting start, a previously planned meeting date, or the later publication date of the minutes. The original project's August 2025 event used the superseded 5–7 August schedule. The official resolution states that the actual meeting was **4–6 August**, with the public decision on **6 August 2025**. All downstream analyses now use the corrected date.

Each link below is official RBI material containing the relevant decision. Some are Governor's statements, later minutes reproducing the original resolution, or the RBI's monthly information review. Those publication types are identified so that their publication dates are not confused with the event dates.

| Event date | Decision | Change (bps) | Repo after (%) | Official RBI source |
|---|---|---:|---:|---|
| 2023-02-08 | Hike | +25 | 6.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=55178) |
| 2023-04-06 | Hold | 0 | 6.50 | [Governor's statement](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=55471) |
| 2023-06-08 | Hold | 0 | 6.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=55814) |
| 2023-08-10 | Hold | 0 | 6.50 | [Governor's statement](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=56175) |
| 2023-10-06 | Hold | 0 | 6.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=56502) |
| 2023-12-08 | Hold | 0 | 6.50 | [Governor's statement](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=56887) |
| 2024-02-08 | Hold | 0 | 6.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=57275) |
| 2024-04-05 | Hold | 0 | 6.50 | [Minutes reproducing the April 5 resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=57735) |
| 2024-06-07 | Hold | 0 | 6.50 | [June Monetary and Credit Information Review](https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=22453) |
| 2024-08-08 | Hold | 0 | 6.50 | [Governor's statement](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=58448) |
| 2024-10-09 | Hold | 0 | 6.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=58850) |
| 2024-12-06 | Hold | 0 | 6.50 | [Minutes reproducing the December 6 resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=59347) |
| 2025-02-07 | Cut | −25 | 6.25 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=59692) |
| 2025-04-09 | Cut | −25 | 6.00 | [Governor's statement](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60177) |
| 2025-06-06 | Cut | −50 | 5.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60604) |
| 2025-08-06 | Hold | 0 | 5.50 | [Actual August 4–6 meeting resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60957) |
| 2025-10-01 | Hold | 0 | 5.50 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=61332) |
| 2025-12-05 | Cut | −25 | 5.25 | [Resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=61749) |

The validator checks the frozen event dates, unique event identifiers, actual meeting boundaries, signed decision labels, repo-rate continuity, basis-point arithmetic, and event-specific official URLs. These tests preserve a source-reconciled table; they do not claim to re-download and authenticate all RBI pages each time the pipeline runs.

## Validation scope and remaining limitations

The data builder rejects duplicate keys, wrong symbols or metadata, non-positive prices, non-finite market fields, partial missing OHLC records, inconsistent OHLC ordering, negative volume/actions, unequal observed asset calendars, and missing non-initial returns. It requires all policy announcement dates to occur on the validated market calendar. It retains the initial missing return per asset and records 14 daily price movements exceeding 10% in absolute value for review. Those flags are not automatically classed as errors.

Calendar validation compares the observed date sets across the eight assets after the documented repair. A date jointly omitted from all eight Yahoo series would not be discovered by this check. No complete independent reconstruction of NSE's special-session/holiday calendar is claimed. Similarly, the data do not provide point-in-time vendor vintages; a present-day download can contain later corrections and retrospective share adjustments.

The six-bank universe is a selected sample, not the whole Indian banking sector. All four rate-cut events occur in 2025, all six 2024 events are holds, and only one hike is observed. A repo hold can still coincide with changes in stance, liquidity measures or other policy news. The event categories therefore do not isolate a policy surprise or establish a causal effect on share prices.

These are public-source research snapshots. Public availability does not itself establish unrestricted redistribution or commercial-use rights. Provider terms apply; production use would require suitable licensed market data and a separate assessment of use permissions.
