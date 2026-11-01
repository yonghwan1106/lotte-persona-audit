# Gate score

Decision: **NO SWITCH**

Panel n: 300. Same 300 real answers cell MAE: {'ever': 6.86, 'weekly': 5.03, 'carb': 3.69, 'average': 5.19}

| cond | item | cell MAE | constant | beats constant | worth N | AUC | floor same 300 | floor all demog same 300 | ceiling test | bias pp | underdisp | gender gap panel | gender gap real | age slope panel | age slope real | pattern |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0 | ever | 28.56 | 18.61 | False | no value | None | None | None | 0.773 | 26.17 | 0.0 | 0.0 | 2.424 | 0.0 | -12.758 | False |
| C0 | weekly | 19.39 | 7.63 | False | no value | None | None | None | 0.779 | 19.33 | 0.0 | 0.0 | -0.588 | 0.0 | -4.194 | False |
| C0 | carb | 5.42 | 4.14 | False | no value | None | None | None | 0.569 | 3.47 | 0.0 | 0.0 | -5.374 | 0.0 | -2.333 | False |
| C1 | ever | 18.16 | 18.61 | True | <100 | 0.754 | 0.782 | 0.779 | 0.773 | 19.3 | 0.779 | -5.785 | 2.424 | -9.335 | -12.758 | True |
| C1 | weekly | 18.18 | 7.63 | False | no value | 0.756 | 0.755 | 0.753 | 0.779 | 18.81 | 1.381 | -5.846 | -0.588 | -6.553 | -4.194 | True |
| C1 | carb | 3.73 | 4.14 | True | about 431 | 0.699 | 0.735 | 0.608 | 0.569 | 3.16 | 0.733 | -5.179 | -5.374 | -1.942 | -2.333 | True |
| C2 | ever | 20.25 | 18.61 | False | no value | 0.753 | 0.782 | 0.779 | 0.773 | 20.97 | 0.672 | -4.779 | 2.424 | -8.121 | -12.758 | True |
| C2 | weekly | 19.48 | 7.63 | False | no value | 0.757 | 0.755 | 0.753 | 0.779 | 19.86 | 1.322 | -5.513 | -0.588 | -6.296 | -4.194 | True |
| C2 | carb | 3.94 | 4.14 | True | about 340 | 0.657 | 0.735 | 0.608 | 0.569 | 3.58 | 0.788 | -5.189 | -5.374 | -2.145 | -2.333 | True |

## Average over items

| cond | average cell MAE | constant | worth N |
|---|---|---|---|
| C0 | 17.79 | 10.13 | no value |
| C1 | 13.36 | 10.13 | no value |
| C2 | 14.56 | 10.13 | no value |
