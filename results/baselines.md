# Baselines (test split, psfwt)

Rows: {'train': 2921, 'calibration': 632, 'test': 2321}. Seed 42. Allowlist size 38.

## Cell MAE, pp

| item | constant | n=100 raw | n=100 shrunk | n=250 raw | n=250 shrunk | n=500 raw | n=500 shrunk | n=1000 raw | n=1000 shrunk | all train raw |
|---|---|---|---|---|---|---|---|---|---|---|
| ever | 18.61 | 17.7 | 17.38 | 11.06 | 14.67 | 8.57 | 11.97 | 6.59 | 9.11 | 5.18 |
| weekly | 7.63 | 12.21 | 7.61 | 8.3 | 6.42 | 6.34 | 5.43 | 4.99 | 4.36 | 4.2 |
| carb | 4.14 | 9.51 | 4.99 | 6.78 | 4.21 | 4.78 | 3.6 | 3.65 | 3.1 | 2.73 |
| average | 10.13 | 13.14 | 9.99 | 8.71 | 8.43 | 6.56 | 7.0 | 5.08 | 5.52 | 4.04 |

## AUC on the test split

| item | model | AUC | 95% CI (unit bootstrap) | within-unit AUC | usable units |
|---|---|---|---|---|---|
| ever | floor_age_sex | 0.741 | [0.709, 0.776] | 0.777 | 152 |
| ever | floor_all_c1_demographics | 0.737 | [0.7, 0.781] | 0.76 | 152 |
| ever | ceiling_allowlist_logistic | 0.773 | [0.738, 0.813] | 0.711 | 152 |
| ever | ceiling_allowlist_gbm | 0.827 | [0.794, 0.862] | 0.755 | 152 |
| weekly | floor_age_sex | 0.685 | [0.611, 0.772] | 0.821 | 57 |
| weekly | floor_all_c1_demographics | 0.718 | [0.648, 0.784] | 0.799 | 57 |
| weekly | ceiling_allowlist_logistic | 0.779 | [0.715, 0.837] | 0.785 | 57 |
| weekly | ceiling_allowlist_gbm | 0.804 | [0.732, 0.857] | 0.766 | 57 |
| carb | floor_age_sex | 0.653 | [0.602, 0.701] | 0.594 | 102 |
| carb | floor_all_c1_demographics | 0.602 | [0.544, 0.652] | 0.554 | 102 |
| carb | ceiling_allowlist_logistic | 0.569 | [0.522, 0.622] | 0.482 | 102 |
| carb | ceiling_allowlist_gbm | 0.597 | [0.548, 0.644] | 0.495 | 102 |
