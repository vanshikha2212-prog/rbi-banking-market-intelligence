/* ============================================================
   RBI BANKING MARKET INTELLIGENCE
   SAS EVENT-STUDY VALIDATION
   ============================================================ */

/* ------------------------------------------------------------
   1. Import event-study results
   ------------------------------------------------------------ */

proc import
    datafile="data/processed/event_study_results.csv"
    out=event_study
    dbms=csv
    replace;
    guessingrows=max;
    getnames=yes;
run;


/* ------------------------------------------------------------
   2. Descriptive statistics
   ------------------------------------------------------------ */

proc means data=event_study
    n
    mean
    std
    min
    max;
    
    var
        car_minus_1_plus_1
        car_minus_2_plus_2
        car_minus_5_plus_5;
run;


/* ------------------------------------------------------------
   3. Test mean CAR against zero
   ------------------------------------------------------------ */

proc ttest data=event_study h0=0;

    var car_minus_1_plus_1;

run;


/* ------------------------------------------------------------
   4. CAR by bank type
   ------------------------------------------------------------ */

proc means data=event_study
    n
    mean
    std;

    class bank_type;

    var car_minus_1_plus_1;

run;


/* ------------------------------------------------------------
   5. CAR by RBI decision
   ------------------------------------------------------------ */

proc sql;

    select
        decision,
        count(*) as observations,
        mean(car_minus_1_plus_1) as mean_car
    from event_study
    group by decision;

quit;


/* ------------------------------------------------------------
   6. Export summary statistics
   ------------------------------------------------------------ */

proc means data=event_study
    noprint;

    var car_minus_1_plus_1;

    output out=sas_car_summary
        n=n
        mean=mean_car
        std=std_car;

run;

proc print data=sas_car_summary;
run;