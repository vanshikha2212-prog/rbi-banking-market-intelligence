"""Figures with explicit units, horizons, and policy-event sample counts."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def create_figures(output_dir, tables) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white"})
    palette = {"Cut": "#087f75", "Hold": "#557287", "Hike": "#b87933"}
    paths = []

    def save(figure, name):
        path = directory / f"{name}.png"
        figure.savefig(path, dpi=170, bbox_inches="tight", metadata={"Software": "RBI Banking Market Intelligence 2.0"})
        plt.close(figure)
        paths.append(path)

    means = tables["event_means"]
    primary = means[means.benchmark.eq("^NSEI") & means.window.eq("[-1,+1]")].sort_values("event_date")
    fig, ax = plt.subplots(figsize=(11.5, 4.7))
    x = np.arange(len(primary))
    ax.bar(x, primary.mean_car, color=[palette[d] for d in primary.decision], width=.7)
    ax.axhline(0, color="#8d9b9e", linewidth=.8)
    ax.set_xticks(x, pd.to_datetime(primary.event_date).dt.strftime("%d %b %y"), rotation=55, ha="right")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Mean cumulative abnormal return")
    ax.set_title(f"{len(primary)} announcements, six banks per event", loc="left", fontweight="bold", pad=20)
    for decision, color in palette.items():
        ax.bar([], [], color=color, label=f"{decision} (n={int(primary.decision.eq(decision).sum())} events)")
    ax.legend(frameon=False, ncols=3, loc="upper left")
    fig.text(.125, -.12, "Nifty 50 market model · [−1,+1] trading days · price returns · descriptive association", fontsize=9, color="#52676f")
    save(fig, "event_timeline")

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    for index, decision in enumerate(("Cut", "Hold", "Hike")):
        values = primary.loc[primary.decision.eq(decision), "mean_car"].to_numpy()
        if not len(values):
            continue
        # Fixed offsets expose each event without nondeterministic jitter.
        offsets = np.linspace(-.13, .13, len(values)) if len(values) > 1 else np.array([0.0])
        ax.scatter(index + offsets, values, s=43, color=palette[decision], alpha=.8, zorder=3)
        average = values.mean()
        ax.plot([index-.2, index+.2], [average, average], color="#182a37", linewidth=2.5)
        if len(values) >= 2:
            half = stats.t.ppf(.975, len(values)-1) * values.std(ddof=1) / np.sqrt(len(values))
            ax.errorbar(index, average, yerr=half, fmt="none", ecolor="#182a37", capsize=5, linewidth=1.3)
    ax.axhline(0, color="#a2adae", linewidth=.8)
    ax.set_xticks(range(3), [f"{d}\n{int(primary.decision.eq(d).sum())} events" for d in ("Cut", "Hold", "Hike")])
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Event-level mean CAR")
    ax.set_title("Policy groups have very different sample sizes", loc="left", fontweight="bold", pad=17)
    fig.text(.125, -.07, "Dots: announcements. Line: group mean. Whiskers: pointwise 95% t intervals.\nNo interval for the single hike. Nifty 50 · [−1,+1]. All four cuts occurred in 2025.", fontsize=9, color="#52676f")
    save(fig, "decision_event_distribution")

    volatility = tables["event_volatility"]
    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    for name, group in volatility[volatility.converged.eq(True)].groupby("bank_name", sort=True):
        group = group.sort_values("event_date")
        ax.plot(pd.to_datetime(group.event_date), group.garch_volatility, marker="o", markersize=3.5, linewidth=1.3, label=name)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Forecast daily standard deviation")
    ax.set_xlabel("Forecast target: announcement trading day")
    ax.set_title("Past-only GARCH(1,1) forecasts", loc="left", fontweight="bold", pad=17)
    ax.legend(frameon=False, ncols=3, loc="upper left", fontsize=8)
    fig.text(.125, -.07, "Student-t innovations · expanding history ending at the previous trading close · no annualisation", fontsize=9, color="#52676f")
    save(fig, "event_volatility")

    metrics = tables["model_metrics"]
    fitted = metrics[metrics.accuracy.notna()].copy()
    labels = {"dummy_majority": "Majority baseline", "logistic_regression": "Logistic regression", "random_forest": "Random forest"}
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.5))
    for ax, metric, title in zip(axes, ("balanced_accuracy", "roc_auc"), ("Balanced accuracy", "ROC AUC")):
        x = np.arange(len(fitted))
        ax.bar(x, fitted[metric], color=["#9ba9af", "#087f75", "#7664a3"][:len(fitted)], width=.6)
        uncertainty = tables["model_uncertainty"]
        for pos, row in enumerate(fitted.itertuples(index=False)):
            interval = uncertainty[uncertainty.model.eq(row.model) & uncertainty.metric.eq(metric)]
            if not interval.empty:
                lower, upper = interval.iloc[0][["ci_lower", "ci_upper"]]
                if np.isfinite([lower, upper]).all():
                    ax.plot([pos, pos], [lower, upper], color="#182a37", linewidth=1.3)
                    ax.plot([pos-.07, pos+.07], [lower, lower], color="#182a37")
                    ax.plot([pos-.07, pos+.07], [upper, upper], color="#182a37")
        ax.axhline(.5, linestyle="--", color="#687c86", linewidth=.8)
        ax.set_xticks(x, [labels[name].replace(" ", "\n", 1) for name in fitted.model])
        ax.set_ylim(0, 1.03)
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    test_events = int(fitted.n_test_events.iloc[0])
    test_rows = int(fitted.n_test_rows.iloc[0])
    fig.suptitle(f"2025 holdout: {test_events} announcements, {test_rows} bank-event rows", x=.125, ha="left", fontweight="bold", y=1.03)
    fig.text(.125, -.11, "Target: positive CAR[0,+1]; features available at the previous close. Whiskers resample whole events.\nIntervals are exploratory and unstable with six events; the holdout was not used to tune model settings.", fontsize=9, color="#52676f")
    save(fig, "prediction_holdout")
    return paths
