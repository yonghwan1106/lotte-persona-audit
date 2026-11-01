# A2 flags: can in-run signals name wrong cells before real data

36 item by cell units, Terra C2. Error: absolute cell error of E4 from 200 real draws, averaged, against the panel excluded truth. Stored answers only. No correction across signals. Plan: config/prereg_stage4.json.

panel_level is a comparator added by the worker: it needs no second model.

| signal | usable units | Spearman | interval | within item Spearman | interval | overlap top 9 | random mean | random 95 | p one sided | minus level interval | names wrong cells |
|---|---|---|---|---|---|---|---|---|---|---|---|
| terra_minus_luna | 36 | -0.278 | [-0.489, 0.002] | -0.182 | [-0.326, 0.219] | 1 | 2.247 | [0, 5] | 0.94705 | [-0.719, -0.09] | False |
| c1_minus_c2 | 36 | 0.188 | [-0.147, 0.432] | -0.049 | [-0.329, 0.289] | 3 | 2.247 | [0, 5] | 0.40093 | [-0.337, 0.263] | False |
| repeat_sd | 36 | 0.263 | [-0.077, 0.448] | 0.042 | [-0.238, 0.364] | 2 | 2.247 | [0, 5] | 0.73561 | [-0.207, 0.23] | False |
| panel_level | 36 | 0.154 | [-0.088, 0.439] | 0.002 | [-0.175, 0.401] | 3 | 2.247 | [0, 5] | 0.40093 | - | None |

Whole test truth sensitivity: terra_minus_luna Spearman -0.18 overlap 1, c1_minus_c2 Spearman -0.009 overlap 2, repeat_sd Spearman 0.255 overlap 2, panel_level Spearman 0.184 overlap 2

Error by item: {'ever': {'mean_pp': 7.588, 'max_pp': 15.881}, 'weekly': {'mean_pp': 6.651, 'max_pp': 15.185}, 'carb': {'mean_pp': 4.011, 'max_pp': 11.126}}
