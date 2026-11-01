# Gate score

Decision: **NO SWITCH**

Panel n: 300. Same 300 real answers cell MAE: {'ever': 6.86, 'weekly': 5.03, 'carb': 3.69, 'average': 5.19}

| cond | item | cell MAE | constant | beats constant | worth N | AUC | floor same 300 | floor all demog same 300 | ceiling test | bias pp | underdisp | gender gap panel | gender gap real | age slope panel | age slope real | pattern |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0 | ever | 27.1 | 18.61 | False | no value | None | None | None | 0.773 | 23.98 | 0.0 | 0.0 | 2.424 | 0.0 | -12.758 | False |
| C0 | weekly | 21.69 | 7.63 | False | no value | None | None | None | 0.779 | 21.63 | 0.0 | 0.0 | -0.588 | 0.0 | -4.194 | False |
| C0 | carb | 8.92 | 4.14 | False | no value | None | None | None | 0.569 | 8.13 | 0.0 | 0.0 | -5.374 | 0.0 | -2.333 | False |
| C1 | ever | 17.01 | 18.61 | True | about 106 | 0.775 | 0.782 | 0.779 | 0.773 | 17.7 | 0.755 | -5.067 | 2.424 | -9.364 | -12.758 | True |
| C1 | weekly | 18.96 | 7.63 | False | no value | 0.762 | 0.755 | 0.753 | 0.779 | 19.3 | 1.52 | -5.657 | -0.588 | -7.337 | -4.194 | True |
| C1 | carb | 9.24 | 4.14 | False | no value | 0.746 | 0.735 | 0.608 | 0.569 | 9.67 | 1.243 | -6.485 | -5.374 | -3.579 | -2.333 | True |
| C2 | ever | 17.07 | 18.61 | True | about 105 | 0.794 | 0.782 | 0.779 | 0.773 | 17.65 | 0.76 | -5.415 | 2.424 | -9.559 | -12.758 | True |
| C2 | weekly | 17.5 | 7.63 | False | no value | 0.8 | 0.755 | 0.753 | 0.779 | 17.81 | 1.495 | -5.498 | -0.588 | -7.204 | -4.194 | True |
| C2 | carb | 9.2 | 4.14 | False | no value | 0.728 | 0.735 | 0.608 | 0.569 | 9.56 | 1.233 | -6.677 | -5.374 | -3.565 | -2.333 | True |

## Average over items

| cond | average cell MAE | constant | worth N |
|---|---|---|---|
| C0 | 19.24 | 10.13 | no value |
| C1 | 15.07 | 10.13 | no value |
| C2 | 14.59 | 10.13 | no value |
