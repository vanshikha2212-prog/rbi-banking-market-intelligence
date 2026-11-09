# Research design

## Questions

1. How are RBI repo-rate announcements associated with abnormal returns in six Indian banking stocks?
2. Which banks respond differently, and is the public-minus-private difference supported when paired within the same announcement?
3. Can pre-announcement information predict the sign of CAR `[0,+1]` better than simple baselines?

## Event study and inference

Each market model uses 250 trading returns ending at day −6. Nifty 50 is primary; Nifty Bank and 120/180-day estimation histories are sensitivities.

The policy event is the sampling unit. Banks are averaged within an event before decision comparisons. Public/private tests use paired within-event differences. The report includes effect sizes, event bootstrap intervals, permutation or Wilcoxon tests, Holm adjustments, leave-one-event-out estimates, and every declared COVID/off-cycle exclusion.

## Prediction

Previous-close features cover bank/market momentum, volatility, downside volatility, volume surprise, beta/correlation, group momentum, known repo level, prior policy change, elapsed time, bank type, and past-only GARCH volatility.

After 24 events, one later complete event is predicted at a time. Preprocessing and sigmoid calibration fit only on earlier event groups. Whole-event bootstrap intervals compare fixed models with simple baselines.

Prediction scores, statistical significance, and causality are separate claims.
