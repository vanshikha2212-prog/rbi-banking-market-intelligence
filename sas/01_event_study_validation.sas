/* Optional, unexecuted-until-verified SAS cross-check.
   Run the corrected Python pipeline first, then run SAS from the repo root.
   These primary-window exports include bank metadata and event-level means.
   This script does not independently validate the underlying market prices.
   Keep SAS marked "not executed" until a real SAS log and results are saved. */

proc import datafile="outputs/tableau/sas_event_results.csv"
    out=bank_event_results dbms=csv replace;
    guessingrows=max;
    getnames=yes;
run;

proc import datafile="outputs/tableau/sas_event_means.csv"
    out=event_means dbms=csv replace;
    guessingrows=max;
    getnames=yes;
run;

/* These exports are restricted to Nifty 50 and the [-1,+1] three-day window.
   Bank-event descriptive statistics are not independent policy-event tests. */
proc means data=bank_event_results n mean std min max;
    class bank_type;
    var car absolute_car;
run;

proc sql;
    select count(distinct event_id) as independent_policy_events,
           count(*) as bank_event_records
    from bank_event_results;
quit;

/* One record per announcement: primary one-sample check against zero. */
proc means data=event_means n mean std min max;
    var mean_car mean_absolute_car;
run;

proc ttest data=event_means h0=0;
    var mean_car;
run;

/* Report descriptive decision means; one hike cannot support group inference. */
proc means data=event_means n mean std;
    class decision;
    var mean_car;
run;

/* Save an event-level summary for comparison with Python, not a claim of
   completed validation. Do not infer causality from any statistical result. */
proc means data=event_means noprint;
    var mean_car;
    output out=sas_event_summary n=n_events mean=mean_car std=std_event_mean_car;
run;
proc print data=sas_event_summary;
run;
