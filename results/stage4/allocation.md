# A1 allocation: does the panel help spend 200 people

Stored answers only. The calibration pool stands in for the population. Intervals are across 200 draws with the pool and the test panel fixed. Not comparable digit for digit with stage 2, whose row draws and weights differ. Plan: config/prereg_stage4.json.

## Allocations (n per cell)

| allocation | 41 | 42 | 51 | 52 | 61 | 62 | 71 | 72 | 81 | 82 | 91 | 92 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| equal | 17 | 17 | 17 | 17 | 17 | 17 | 17 | 17 | 16 | 16 | 16 | 16 |
| proportional | 14 | 11 | 18 | 15 | 20 | 17 | 19 | 18 | 19 | 17 | 13 | 19 |
| panel_neyman | 15 | 11 | 18 | 15 | 21 | 17 | 20 | 18 | 19 | 16 | 13 | 17 |
| reference_neyman | 18 | 13 | 21 | 16 | 23 | 19 | 20 | 18 | 18 | 16 | 7 | 11 |
| pool rows (cap) | 26 | 28 | 37 | 50 | 40 | 52 | 82 | 91 | 70 | 110 | 22 | 24 |

Reference p sources: {'ever': 'train split', 'weekly': 'train split', 'carb': 'a2024 A15_1 in {7,8}'}.

## Reading fixed in advance

- Panel helps over proportional: False (R1, panel excluded truth, 3 item cell MAE, panel Neyman minus proportional +0.010 [-0.339, +0.415]).
- Panel adds over the reference: False (same metric, panel Neyman minus reference Neyman +0.056 [-0.719, +0.904]).

## R1, panel_excluded, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 7.75 | +0.009 [-1.570, +2.256] |
| equal | weekly | 7.036 | -0.183 [-2.731, +1.811] |
| equal | carb | 5.295 | -0.057 [-1.109, +2.063] |
| equal | average | 6.693 | -0.077 [-1.203, +1.237] |
| proportional | ever | 7.741 | - |
| proportional | weekly | 7.218 | - |
| proportional | carb | 5.352 | - |
| proportional | average | 6.77 | - |
| panel_neyman | ever | 7.779 | +0.038 [-0.692, +1.201] |
| panel_neyman | weekly | 7.231 | +0.012 [-0.993, +1.223] |
| panel_neyman | carb | 5.331 | -0.021 [-0.489, +0.290] |
| panel_neyman | average | 6.78 | +0.010 [-0.339, +0.415] |
| reference_neyman | ever | 7.676 | -0.064 [-1.768, +1.754] |
| reference_neyman | weekly | 7.228 | +0.010 [-1.826, +1.972] |
| reference_neyman | carb | 5.27 | -0.082 [-1.002, +0.829] |
| reference_neyman | average | 6.725 | -0.046 [-0.967, +0.743] |
| panel_neyman_by_item | ever | 7.905 | +0.164 [-2.664, +2.504] |
| panel_neyman_by_item | weekly | 7.226 | +0.008 [-1.798, +1.627] |
| panel_neyman_by_item | carb | 5.312 | -0.040 [-0.911, +0.985] |
| panel_neyman_by_item | average | 6.815 | +0.044 [-1.103, +1.090] |
| reference_neyman_by_item | ever | 7.833 | +0.093 [-1.720, +1.706] |
| reference_neyman_by_item | weekly | 7.985 | +0.767 [-2.144, +4.068] |
| reference_neyman_by_item | carb | 5.325 | -0.027 [-1.166, +1.962] |
| reference_neyman_by_item | average | 7.048 | +0.277 [-0.861, +1.590] |

Panel Neyman minus reference Neyman: ever +0.103 [-1.650, +1.675], weekly +0.003 [-1.571, +1.414], carb +0.061 [-0.828, +0.800], average +0.056 [-0.719, +0.904]

## R1, panel_excluded, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 4.314 | +0.116 [-2.274, +3.024] |
| equal | weekly | 5.923 | -0.118 [-3.001, +2.511] |
| equal | carb | 3.45 | +0.029 [-1.388, +1.635] |
| equal | average | 4.562 | +0.009 [-1.048, +1.094] |
| proportional | ever | 4.198 | - |
| proportional | weekly | 6.041 | - |
| proportional | carb | 3.421 | - |
| proportional | average | 4.554 | - |
| panel_neyman | ever | 4.23 | +0.032 [-0.990, +1.143] |
| panel_neyman | weekly | 6.029 | -0.012 [-1.476, +1.334] |
| panel_neyman | carb | 3.426 | +0.004 [-0.587, +0.459] |
| panel_neyman | average | 4.562 | +0.008 [-0.430, +0.432] |
| reference_neyman | ever | 4.163 | -0.035 [-2.316, +2.307] |
| reference_neyman | weekly | 6.067 | +0.025 [-2.404, +2.521] |
| reference_neyman | carb | 3.423 | +0.002 [-1.271, +1.069] |
| reference_neyman | average | 4.551 | -0.003 [-1.087, +0.945] |
| panel_neyman_by_item | ever | 4.22 | +0.022 [-3.085, +2.643] |
| panel_neyman_by_item | weekly | 6.038 | -0.003 [-2.064, +2.476] |
| panel_neyman_by_item | carb | 3.418 | -0.003 [-1.339, +1.049] |
| panel_neyman_by_item | average | 4.559 | +0.005 [-1.244, +1.293] |
| reference_neyman_by_item | ever | 4.198 | +0.000 [-2.355, +2.186] |
| reference_neyman_by_item | weekly | 6.842 | +0.801 [-2.196, +4.205] |
| reference_neyman_by_item | carb | 3.448 | +0.026 [-1.416, +1.899] |
| reference_neyman_by_item | average | 4.829 | +0.276 [-0.987, +1.681] |

Panel Neyman minus reference Neyman: ever +0.067 [-2.244, +1.982], weekly -0.037 [-2.183, +1.740], carb +0.003 [-0.836, +0.977], average +0.011 [-0.982, +0.910]

## R1, whole_test, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 8.852 | +0.031 [-1.952, +2.533] |
| equal | weekly | 5.334 | -0.102 [-2.524, +2.052] |
| equal | carb | 4.412 | -0.026 [-1.081, +1.554] |
| equal | average | 6.199 | -0.032 [-1.092, +1.200] |
| proportional | ever | 8.821 | - |
| proportional | weekly | 5.436 | - |
| proportional | carb | 4.438 | - |
| proportional | average | 6.232 | - |
| panel_neyman | ever | 8.852 | +0.031 [-0.862, +1.483] |
| panel_neyman | weekly | 5.43 | -0.006 [-0.965, +1.072] |
| panel_neyman | carb | 4.424 | -0.014 [-0.561, +0.304] |
| panel_neyman | average | 6.235 | +0.004 [-0.409, +0.500] |
| reference_neyman | ever | 8.716 | -0.105 [-2.027, +1.873] |
| reference_neyman | weekly | 5.406 | -0.030 [-1.714, +1.690] |
| reference_neyman | carb | 4.359 | -0.079 [-1.226, +0.733] |
| reference_neyman | average | 6.16 | -0.071 [-0.874, +0.765] |
| panel_neyman_by_item | ever | 8.953 | +0.132 [-2.999, +2.471] |
| panel_neyman_by_item | weekly | 5.414 | -0.021 [-1.545, +1.371] |
| panel_neyman_by_item | carb | 4.412 | -0.026 [-1.035, +0.969] |
| panel_neyman_by_item | average | 6.26 | +0.028 [-1.072, +1.042] |
| reference_neyman_by_item | ever | 8.883 | +0.061 [-2.287, +2.013] |
| reference_neyman_by_item | weekly | 6.149 | +0.713 [-1.897, +3.907] |
| reference_neyman_by_item | carb | 4.415 | -0.023 [-1.300, +1.527] |
| reference_neyman_by_item | average | 6.482 | +0.251 [-0.857, +1.347] |

Panel Neyman minus reference Neyman: ever +0.136 [-1.825, +1.775], weekly +0.024 [-1.285, +1.407], carb +0.065 [-0.567, +0.948], average +0.075 [-0.655, +0.777]

## R1, whole_test, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 6.837 | +0.131 [-2.344, +3.024] |
| equal | weekly | 3.42 | -0.027 [-3.001, +2.292] |
| equal | carb | 3.201 | +0.016 [-1.388, +1.550] |
| equal | average | 4.486 | +0.040 [-0.938, +1.341] |
| proportional | ever | 6.707 | - |
| proportional | weekly | 3.447 | - |
| proportional | carb | 3.185 | - |
| proportional | average | 4.446 | - |
| panel_neyman | ever | 6.724 | +0.017 [-0.990, +1.243] |
| panel_neyman | weekly | 3.41 | -0.037 [-1.476, +1.234] |
| panel_neyman | carb | 3.187 | +0.002 [-0.587, +0.413] |
| panel_neyman | average | 4.44 | -0.006 [-0.412, +0.432] |
| reference_neyman | ever | 6.736 | +0.029 [-2.316, +2.674] |
| reference_neyman | weekly | 3.411 | -0.036 [-2.468, +2.362] |
| reference_neyman | carb | 3.177 | -0.008 [-1.271, +1.069] |
| reference_neyman | average | 4.441 | -0.005 [-1.086, +0.811] |
| panel_neyman_by_item | ever | 6.775 | +0.068 [-3.168, +2.679] |
| panel_neyman_by_item | weekly | 3.381 | -0.066 [-2.250, +2.476] |
| panel_neyman_by_item | carb | 3.178 | -0.007 [-1.339, +1.063] |
| panel_neyman_by_item | average | 4.445 | -0.002 [-1.145, +1.255] |
| reference_neyman_by_item | ever | 6.734 | +0.027 [-2.355, +2.269] |
| reference_neyman_by_item | weekly | 4.148 | +0.701 [-1.962, +4.065] |
| reference_neyman_by_item | carb | 3.204 | +0.019 [-1.416, +1.899] |
| reference_neyman_by_item | average | 4.696 | +0.249 [-0.798, +1.543] |

Panel Neyman minus reference Neyman: ever -0.013 [-2.582, +1.982], weekly -0.000 [-1.914, +1.740], carb +0.011 [-0.911, +0.977], average -0.001 [-0.692, +0.930]

## R1, pool_own, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 7.673 | +0.004 [-1.261, +1.224] |
| equal | weekly | 7.371 | -0.083 [-1.484, +1.368] |
| equal | carb | 3.174 | -0.170 [-1.566, +0.818] |
| equal | average | 6.073 | -0.083 [-0.762, +0.643] |
| proportional | ever | 7.669 | - |
| proportional | weekly | 7.454 | - |
| proportional | carb | 3.344 | - |
| proportional | average | 6.156 | - |
| panel_neyman | ever | 7.671 | +0.002 [-0.498, +0.559] |
| panel_neyman | weekly | 7.452 | -0.002 [-0.435, +0.650] |
| panel_neyman | carb | 3.318 | -0.026 [-0.446, +0.298] |
| panel_neyman | average | 6.147 | -0.009 [-0.301, +0.280] |
| reference_neyman | ever | 7.583 | -0.086 [-1.248, +0.851] |
| reference_neyman | weekly | 7.372 | -0.082 [-1.130, +0.878] |
| reference_neyman | carb | 3.209 | -0.135 [-1.163, +0.539] |
| reference_neyman | average | 6.054 | -0.101 [-0.713, +0.501] |
| panel_neyman_by_item | ever | 7.772 | +0.103 [-1.525, +1.987] |
| panel_neyman_by_item | weekly | 7.393 | -0.060 [-1.151, +0.839] |
| panel_neyman_by_item | carb | 3.251 | -0.093 [-1.146, +0.640] |
| panel_neyman_by_item | average | 6.139 | -0.017 [-0.862, +0.702] |
| reference_neyman_by_item | ever | 7.749 | +0.080 [-1.073, +1.531] |
| reference_neyman_by_item | weekly | 7.471 | +0.017 [-1.405, +1.546] |
| reference_neyman_by_item | carb | 3.188 | -0.156 [-1.684, +0.814] |
| reference_neyman_by_item | average | 6.136 | -0.020 [-0.822, +0.699] |

Panel Neyman minus reference Neyman: ever +0.088 [-0.829, +1.101], weekly +0.080 [-0.821, +1.126], carb +0.109 [-0.526, +1.007], average +0.092 [-0.430, +0.733]

## R1, pool_own, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 2.652 | +0.092 [-2.184, +2.812] |
| equal | weekly | 2.34 | +0.106 [-2.391, +2.524] |
| equal | carb | 1.412 | -0.109 [-1.608, +1.116] |
| equal | average | 2.134 | +0.030 [-1.262, +1.224] |
| proportional | ever | 2.56 | - |
| proportional | weekly | 2.234 | - |
| proportional | carb | 1.52 | - |
| proportional | average | 2.105 | - |
| panel_neyman | ever | 2.606 | +0.046 [-0.948, +1.140] |
| panel_neyman | weekly | 2.226 | -0.008 [-1.357, +1.147] |
| panel_neyman | carb | 1.481 | -0.039 [-0.571, +0.402] |
| panel_neyman | average | 2.104 | -0.000 [-0.594, +0.651] |
| reference_neyman | ever | 2.445 | -0.115 [-2.437, +2.316] |
| reference_neyman | weekly | 2.145 | -0.089 [-2.164, +1.805] |
| reference_neyman | carb | 1.363 | -0.157 [-1.268, +0.749] |
| reference_neyman | average | 1.985 | -0.120 [-1.401, +1.023] |
| panel_neyman_by_item | ever | 2.507 | -0.053 [-2.386, +2.671] |
| panel_neyman_by_item | weekly | 2.145 | -0.089 [-1.952, +1.662] |
| panel_neyman_by_item | carb | 1.424 | -0.097 [-1.521, +0.860] |
| panel_neyman_by_item | average | 2.025 | -0.080 [-1.291, +1.072] |
| reference_neyman_by_item | ever | 2.578 | +0.018 [-2.049, +2.142] |
| reference_neyman_by_item | weekly | 2.323 | +0.089 [-2.732, +3.781] |
| reference_neyman_by_item | carb | 1.353 | -0.167 [-2.140, +0.997] |
| reference_neyman_by_item | average | 2.085 | -0.020 [-1.289, +1.268] |

Panel Neyman minus reference Neyman: ever +0.160 [-2.027, +2.271], weekly +0.081 [-1.618, +1.878], carb +0.118 [-0.677, +1.341], average +0.120 [-0.980, +1.366]

## shrink, panel_excluded, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 13.892 | -0.532 [-1.663, +0.550] |
| equal | weekly | 7.19 | -0.258 [-2.283, +1.147] |
| equal | carb | 4.787 | -0.075 [-0.983, +0.637] |
| equal | average | 8.623 | -0.289 [-1.119, +0.354] |
| proportional | ever | 14.424 | - |
| proportional | weekly | 7.448 | - |
| proportional | carb | 4.862 | - |
| proportional | average | 8.911 | - |
| panel_neyman | ever | 14.484 | +0.060 [-0.346, +0.444] |
| panel_neyman | weekly | 7.477 | +0.029 [-1.068, +0.981] |
| panel_neyman | carb | 4.852 | -0.010 [-0.446, +0.179] |
| panel_neyman | average | 8.938 | +0.026 [-0.463, +0.462] |
| reference_neyman | ever | 14.923 | +0.499 [-0.507, +1.520] |
| reference_neyman | weekly | 7.686 | +0.239 [-1.253, +2.001] |
| reference_neyman | carb | 4.698 | -0.164 [-1.146, +0.399] |
| reference_neyman | average | 9.103 | +0.191 [-0.520, +0.950] |
| panel_neyman_by_item | ever | 14.643 | +0.218 [-1.009, +1.397] |
| panel_neyman_by_item | weekly | 7.541 | +0.093 [-1.431, +1.433] |
| panel_neyman_by_item | carb | 4.787 | -0.075 [-0.966, +0.423] |
| panel_neyman_by_item | average | 8.99 | +0.079 [-0.600, +0.675] |
| reference_neyman_by_item | ever | 14.867 | +0.443 [-0.655, +1.363] |
| reference_neyman_by_item | weekly | 8.41 | +0.962 [-0.905, +3.343] |
| reference_neyman_by_item | carb | 4.694 | -0.168 [-1.116, +0.446] |
| reference_neyman_by_item | average | 9.323 | +0.412 [-0.239, +1.330] |

Panel Neyman minus reference Neyman: ever -0.439 [-1.229, +0.605], weekly -0.210 [-1.484, +0.895], carb +0.154 [-0.306, +1.048], average -0.165 [-0.692, +0.395]

## shrink, panel_excluded, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 4.215 | -0.180 [-2.498, +2.756] |
| equal | weekly | 5.944 | -0.063 [-3.041, +2.488] |
| equal | carb | 3.435 | -0.042 [-1.414, +1.641] |
| equal | average | 4.531 | -0.095 [-1.146, +1.214] |
| proportional | ever | 4.395 | - |
| proportional | weekly | 6.007 | - |
| proportional | carb | 3.477 | - |
| proportional | average | 4.626 | - |
| panel_neyman | ever | 4.306 | -0.088 [-1.111, +1.167] |
| panel_neyman | weekly | 6.049 | +0.042 [-1.404, +1.417] |
| panel_neyman | carb | 3.448 | -0.030 [-0.617, +0.401] |
| panel_neyman | average | 4.601 | -0.025 [-0.456, +0.387] |
| reference_neyman | ever | 3.491 | -0.903 [-3.427, +2.300] |
| reference_neyman | weekly | 6.421 | +0.414 [-1.936, +2.824] |
| reference_neyman | carb | 3.31 | -0.168 [-1.462, +0.853] |
| reference_neyman | average | 4.408 | -0.219 [-1.168, +1.195] |
| panel_neyman_by_item | ever | 5.191 | +0.797 [-2.223, +3.501] |
| panel_neyman_by_item | weekly | 6.249 | +0.242 [-1.831, +2.672] |
| panel_neyman_by_item | carb | 3.356 | -0.122 [-1.406, +0.967] |
| panel_neyman_by_item | average | 4.932 | +0.306 [-0.967, +1.575] |
| reference_neyman_by_item | ever | 4.482 | +0.087 [-2.112, +2.314] |
| reference_neyman_by_item | weekly | 7.553 | +1.545 [-1.326, +4.525] |
| reference_neyman_by_item | carb | 3.309 | -0.168 [-1.545, +1.699] |
| reference_neyman_by_item | average | 5.115 | +0.488 [-0.690, +1.752] |

Panel Neyman minus reference Neyman: ever +0.815 [-1.810, +2.890], weekly -0.372 [-2.420, +1.400], carb +0.138 [-0.701, +1.122], average +0.194 [-1.019, +1.005]

## shrink, whole_test, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 14.195 | -0.502 [-1.630, +0.570] |
| equal | weekly | 6.482 | -0.265 [-2.044, +0.851] |
| equal | carb | 4.478 | -0.095 [-1.069, +0.698] |
| equal | average | 8.385 | -0.287 [-0.934, +0.442] |
| proportional | ever | 14.697 | - |
| proportional | weekly | 6.747 | - |
| proportional | carb | 4.573 | - |
| proportional | average | 8.672 | - |
| panel_neyman | ever | 14.746 | +0.049 [-0.400, +0.493] |
| panel_neyman | weekly | 6.767 | +0.019 [-0.753, +0.739] |
| panel_neyman | carb | 4.566 | -0.007 [-0.435, +0.194] |
| panel_neyman | average | 8.693 | +0.021 [-0.334, +0.367] |
| reference_neyman | ever | 15.161 | +0.463 [-0.736, +1.625] |
| reference_neyman | weekly | 6.964 | +0.216 [-1.149, +1.737] |
| reference_neyman | carb | 4.488 | -0.084 [-1.168, +0.466] |
| reference_neyman | average | 8.871 | +0.198 [-0.497, +0.868] |
| panel_neyman_by_item | ever | 14.923 | +0.226 [-1.310, +1.431] |
| panel_neyman_by_item | weekly | 6.807 | +0.060 [-1.141, +1.106] |
| panel_neyman_by_item | carb | 4.495 | -0.078 [-1.066, +0.473] |
| panel_neyman_by_item | average | 8.742 | +0.069 [-0.528, +0.605] |
| reference_neyman_by_item | ever | 15.126 | +0.429 [-0.792, +1.403] |
| reference_neyman_by_item | weekly | 7.525 | +0.777 [-0.696, +2.771] |
| reference_neyman_by_item | carb | 4.476 | -0.096 [-1.216, +0.592] |
| reference_neyman_by_item | average | 9.042 | +0.370 [-0.345, +1.027] |

Panel Neyman minus reference Neyman: ever -0.414 [-1.428, +0.630], weekly -0.197 [-1.213, +0.641], carb +0.078 [-0.421, +1.025], average -0.178 [-0.678, +0.365]

## shrink, whole_test, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 6.715 | -0.237 [-2.702, +2.716] |
| equal | weekly | 3.436 | +0.016 [-3.041, +2.249] |
| equal | carb | 3.186 | -0.054 [-1.414, +1.617] |
| equal | average | 4.445 | -0.092 [-1.039, +1.118] |
| proportional | ever | 6.952 | - |
| proportional | weekly | 3.42 | - |
| proportional | carb | 3.24 | - |
| proportional | average | 4.537 | - |
| panel_neyman | ever | 6.806 | -0.146 [-1.175, +1.171] |
| panel_neyman | weekly | 3.423 | +0.003 [-1.594, +1.367] |
| panel_neyman | carb | 3.208 | -0.032 [-0.617, +0.383] |
| panel_neyman | average | 4.479 | -0.058 [-0.469, +0.374] |
| reference_neyman | ever | 5.862 | -1.090 [-3.519, +1.321] |
| reference_neyman | weekly | 3.716 | +0.297 [-2.097, +2.664] |
| reference_neyman | carb | 3.069 | -0.171 [-1.462, +0.853] |
| reference_neyman | average | 4.216 | -0.321 [-1.405, +0.469] |
| panel_neyman_by_item | ever | 7.887 | +0.935 [-2.325, +3.538] |
| panel_neyman_by_item | weekly | 3.556 | +0.136 [-2.246, +2.672] |
| panel_neyman_by_item | carb | 3.116 | -0.124 [-1.406, +1.074] |
| panel_neyman_by_item | average | 4.853 | +0.316 [-0.872, +1.487] |
| reference_neyman_by_item | ever | 7.068 | +0.116 [-2.162, +2.405] |
| reference_neyman_by_item | weekly | 4.758 | +1.338 [-1.610, +4.276] |
| reference_neyman_by_item | carb | 3.072 | -0.168 [-1.545, +1.652] |
| reference_neyman_by_item | average | 4.966 | +0.429 [-0.748, +1.689] |

Panel Neyman minus reference Neyman: ever +0.944 [-1.507, +2.961], weekly -0.293 [-2.280, +1.428], carb +0.139 [-0.701, +1.122], average +0.263 [-0.509, +1.317]

## shrink, pool_own, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 15.078 | -0.320 [-1.312, +0.575] |
| equal | weekly | 6.682 | +0.029 [-1.015, +1.161] |
| equal | carb | 3.482 | -0.133 [-0.970, +0.422] |
| equal | average | 8.414 | -0.141 [-0.823, +0.389] |
| proportional | ever | 15.398 | - |
| proportional | weekly | 6.654 | - |
| proportional | carb | 3.615 | - |
| proportional | average | 8.556 | - |
| panel_neyman | ever | 15.401 | +0.003 [-0.451, +0.356] |
| panel_neyman | weekly | 6.641 | -0.013 [-0.661, +0.349] |
| panel_neyman | carb | 3.598 | -0.016 [-0.257, +0.162] |
| panel_neyman | average | 8.547 | -0.009 [-0.313, +0.183] |
| reference_neyman | ever | 15.755 | +0.357 [-0.654, +1.277] |
| reference_neyman | weekly | 6.726 | +0.073 [-0.833, +0.910] |
| reference_neyman | carb | 3.565 | -0.050 [-0.773, +0.411] |
| reference_neyman | average | 8.682 | +0.127 [-0.428, +0.589] |
| panel_neyman_by_item | ever | 15.651 | +0.253 [-0.988, +1.363] |
| panel_neyman_by_item | weekly | 6.647 | -0.006 [-0.839, +0.674] |
| panel_neyman_by_item | carb | 3.535 | -0.080 [-0.794, +0.348] |
| panel_neyman_by_item | average | 8.611 | +0.055 [-0.452, +0.504] |
| reference_neyman_by_item | ever | 15.727 | +0.329 [-0.668, +1.160] |
| reference_neyman_by_item | weekly | 7.036 | +0.383 [-0.714, +1.395] |
| reference_neyman_by_item | carb | 3.538 | -0.077 [-0.971, +0.492] |
| reference_neyman_by_item | average | 8.767 | +0.211 [-0.280, +0.712] |

Panel Neyman minus reference Neyman: ever -0.354 [-1.178, +0.525], weekly -0.085 [-0.838, +0.759], carb +0.033 [-0.377, +0.669], average -0.135 [-0.501, +0.370]

## shrink, pool_own, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 2.641 | +0.045 [-2.236, +2.701] |
| equal | weekly | 2.33 | +0.076 [-2.332, +2.467] |
| equal | carb | 1.411 | -0.107 [-1.516, +1.061] |
| equal | average | 2.127 | +0.005 [-1.307, +1.263] |
| proportional | ever | 2.596 | - |
| proportional | weekly | 2.254 | - |
| proportional | carb | 1.518 | - |
| proportional | average | 2.123 | - |
| panel_neyman | ever | 2.629 | +0.033 [-0.869, +1.184] |
| panel_neyman | weekly | 2.237 | -0.017 [-1.397, +1.113] |
| panel_neyman | carb | 1.482 | -0.036 [-0.595, +0.383] |
| panel_neyman | average | 2.116 | -0.007 [-0.539, +0.727] |
| reference_neyman | ever | 2.562 | -0.034 [-2.867, +2.945] |
| reference_neyman | weekly | 2.157 | -0.096 [-2.212, +1.861] |
| reference_neyman | carb | 1.392 | -0.126 [-1.363, +0.765] |
| reference_neyman | average | 2.037 | -0.085 [-1.403, +1.219] |
| panel_neyman_by_item | ever | 2.724 | +0.128 [-2.745, +2.617] |
| panel_neyman_by_item | weekly | 2.138 | -0.116 [-1.985, +1.466] |
| panel_neyman_by_item | carb | 1.435 | -0.083 [-1.623, +0.882] |
| panel_neyman_by_item | average | 2.099 | -0.024 [-1.458, +1.157] |
| reference_neyman_by_item | ever | 2.642 | +0.046 [-1.930, +2.156] |
| reference_neyman_by_item | weekly | 2.301 | +0.047 [-3.158, +3.343] |
| reference_neyman_by_item | carb | 1.364 | -0.154 [-1.933, +1.143] |
| reference_neyman_by_item | average | 2.103 | -0.020 [-1.402, +1.309] |

Panel Neyman minus reference Neyman: ever +0.067 [-2.318, +2.692], weekly +0.079 [-1.724, +2.202], carb +0.090 [-0.721, +1.411], average +0.079 [-1.092, +1.421]

## direct, panel_excluded, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 12.844 | -0.080 [-2.343, +2.487] |
| equal | weekly | 9.017 | -0.512 [-2.894, +1.498] |
| equal | carb | 7.572 | -0.167 [-1.639, +1.319] |
| equal | average | 9.811 | -0.253 [-1.341, +0.988] |
| proportional | ever | 12.924 | - |
| proportional | weekly | 9.529 | - |
| proportional | carb | 7.738 | - |
| proportional | average | 10.064 | - |
| panel_neyman | ever | 12.921 | -0.002 [-0.991, +1.244] |
| panel_neyman | weekly | 9.506 | -0.023 [-1.482, +1.144] |
| panel_neyman | carb | 7.714 | -0.024 [-0.531, +0.525] |
| panel_neyman | average | 10.047 | -0.016 [-0.630, +0.607] |
| reference_neyman | ever | 12.625 | -0.299 [-2.337, +1.806] |
| reference_neyman | weekly | 9.178 | -0.351 [-2.583, +1.469] |
| reference_neyman | carb | 7.585 | -0.153 [-1.291, +1.063] |
| reference_neyman | average | 9.796 | -0.268 [-1.321, +0.676] |
| panel_neyman_by_item | ever | 13.259 | +0.335 [-2.389, +2.923] |
| panel_neyman_by_item | weekly | 9.264 | -0.265 [-2.276, +1.454] |
| panel_neyman_by_item | carb | 7.667 | -0.072 [-1.336, +1.063] |
| panel_neyman_by_item | average | 10.063 | -0.000 [-1.023, +1.213] |
| reference_neyman_by_item | ever | 13.157 | +0.233 [-2.114, +2.589] |
| reference_neyman_by_item | weekly | 10.063 | +0.534 [-2.102, +3.167] |
| reference_neyman_by_item | carb | 7.594 | -0.144 [-1.646, +1.212] |
| reference_neyman_by_item | average | 10.271 | +0.208 [-1.029, +1.557] |

Panel Neyman minus reference Neyman: ever +0.297 [-1.430, +2.222], weekly +0.328 [-1.240, +2.276], carb +0.129 [-0.992, +1.179], average +0.251 [-0.585, +1.163]

## direct, panel_excluded, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 4.314 | +0.116 [-2.274, +3.024] |
| equal | weekly | 5.923 | -0.118 [-3.001, +2.511] |
| equal | carb | 3.45 | +0.029 [-1.388, +1.635] |
| equal | average | 4.562 | +0.009 [-1.048, +1.094] |
| proportional | ever | 4.198 | - |
| proportional | weekly | 6.041 | - |
| proportional | carb | 3.421 | - |
| proportional | average | 4.554 | - |
| panel_neyman | ever | 4.23 | +0.032 [-0.990, +1.143] |
| panel_neyman | weekly | 6.029 | -0.012 [-1.476, +1.334] |
| panel_neyman | carb | 3.426 | +0.004 [-0.587, +0.459] |
| panel_neyman | average | 4.562 | +0.008 [-0.430, +0.432] |
| reference_neyman | ever | 4.163 | -0.035 [-2.316, +2.307] |
| reference_neyman | weekly | 6.067 | +0.025 [-2.404, +2.521] |
| reference_neyman | carb | 3.423 | +0.002 [-1.271, +1.069] |
| reference_neyman | average | 4.551 | -0.003 [-1.087, +0.945] |
| panel_neyman_by_item | ever | 4.22 | +0.022 [-3.085, +2.643] |
| panel_neyman_by_item | weekly | 6.038 | -0.003 [-2.064, +2.476] |
| panel_neyman_by_item | carb | 3.418 | -0.003 [-1.339, +1.049] |
| panel_neyman_by_item | average | 4.559 | +0.005 [-1.244, +1.293] |
| reference_neyman_by_item | ever | 4.198 | +0.000 [-2.355, +2.186] |
| reference_neyman_by_item | weekly | 7.127 | +1.085 [-1.841, +4.050] |
| reference_neyman_by_item | carb | 3.448 | +0.026 [-1.416, +1.899] |
| reference_neyman_by_item | average | 4.924 | +0.371 [-0.893, +1.692] |

Panel Neyman minus reference Neyman: ever +0.067 [-2.244, +1.982], weekly -0.037 [-2.183, +1.740], carb +0.003 [-0.836, +0.977], average +0.011 [-0.982, +0.910]

## direct, whole_test, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 13.838 | -0.014 [-2.537, +2.532] |
| equal | weekly | 8.524 | -0.542 [-3.276, +1.706] |
| equal | carb | 6.483 | -0.242 [-1.624, +1.043] |
| equal | average | 9.615 | -0.266 [-1.525, +0.953] |
| proportional | ever | 13.852 | - |
| proportional | weekly | 9.066 | - |
| proportional | carb | 6.725 | - |
| proportional | average | 9.881 | - |
| panel_neyman | ever | 13.849 | -0.003 [-0.991, +1.244] |
| panel_neyman | weekly | 9.077 | +0.011 [-1.191, +1.123] |
| panel_neyman | carb | 6.683 | -0.042 [-0.567, +0.502] |
| panel_neyman | average | 9.87 | -0.011 [-0.701, +0.607] |
| reference_neyman | ever | 13.545 | -0.307 [-2.549, +1.684] |
| reference_neyman | weekly | 8.68 | -0.386 [-2.629, +1.602] |
| reference_neyman | carb | 6.505 | -0.221 [-1.357, +0.744] |
| reference_neyman | average | 9.577 | -0.305 [-1.482, +0.699] |
| panel_neyman_by_item | ever | 14.191 | +0.338 [-2.433, +3.011] |
| panel_neyman_by_item | weekly | 8.795 | -0.271 [-2.195, +1.520] |
| panel_neyman_by_item | carb | 6.589 | -0.136 [-1.366, +0.919] |
| panel_neyman_by_item | average | 9.858 | -0.023 [-1.011, +1.182] |
| reference_neyman_by_item | ever | 14.071 | +0.219 [-2.166, +2.529] |
| reference_neyman_by_item | weekly | 8.941 | -0.125 [-2.670, +2.826] |
| reference_neyman_by_item | carb | 6.506 | -0.219 [-1.621, +1.031] |
| reference_neyman_by_item | average | 9.839 | -0.042 [-1.414, +1.299] |

Panel Neyman minus reference Neyman: ever +0.304 [-1.429, +2.125], weekly +0.397 [-1.409, +2.401], carb +0.178 [-0.800, +1.253], average +0.293 [-0.715, +1.359]

## direct, whole_test, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 6.837 | +0.131 [-2.344, +3.024] |
| equal | weekly | 3.42 | -0.027 [-3.001, +2.292] |
| equal | carb | 3.201 | +0.016 [-1.388, +1.550] |
| equal | average | 4.486 | +0.040 [-0.938, +1.341] |
| proportional | ever | 6.707 | - |
| proportional | weekly | 3.447 | - |
| proportional | carb | 3.185 | - |
| proportional | average | 4.446 | - |
| panel_neyman | ever | 6.724 | +0.017 [-0.990, +1.243] |
| panel_neyman | weekly | 3.41 | -0.037 [-1.476, +1.234] |
| panel_neyman | carb | 3.187 | +0.002 [-0.587, +0.413] |
| panel_neyman | average | 4.44 | -0.006 [-0.412, +0.432] |
| reference_neyman | ever | 6.736 | +0.029 [-2.316, +2.674] |
| reference_neyman | weekly | 3.411 | -0.036 [-2.468, +2.362] |
| reference_neyman | carb | 3.177 | -0.008 [-1.271, +1.069] |
| reference_neyman | average | 4.441 | -0.005 [-1.086, +0.811] |
| panel_neyman_by_item | ever | 6.775 | +0.068 [-3.168, +2.679] |
| panel_neyman_by_item | weekly | 3.381 | -0.066 [-2.250, +2.476] |
| panel_neyman_by_item | carb | 3.178 | -0.007 [-1.339, +1.063] |
| panel_neyman_by_item | average | 4.445 | -0.002 [-1.145, +1.255] |
| reference_neyman_by_item | ever | 6.734 | +0.027 [-2.355, +2.269] |
| reference_neyman_by_item | weekly | 4.365 | +0.918 [-1.845, +3.929] |
| reference_neyman_by_item | carb | 3.204 | +0.019 [-1.416, +1.899] |
| reference_neyman_by_item | average | 4.768 | +0.321 [-0.815, +1.542] |

Panel Neyman minus reference Neyman: ever -0.013 [-2.582, +1.982], weekly -0.000 [-1.914, +1.740], carb +0.011 [-0.911, +0.977], average -0.001 [-0.692, +0.930]

## direct, pool_own, cell_mae (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 8.32 | -0.050 [-2.454, +2.413] |
| equal | weekly | 6.608 | -0.241 [-2.992, +2.002] |
| equal | carb | 3.714 | -0.276 [-1.526, +1.127] |
| equal | average | 6.214 | -0.189 [-1.590, +1.062] |
| proportional | ever | 8.37 | - |
| proportional | weekly | 6.849 | - |
| proportional | carb | 3.99 | - |
| proportional | average | 6.403 | - |
| panel_neyman | ever | 8.373 | +0.003 [-0.947, +0.977] |
| panel_neyman | weekly | 6.816 | -0.033 [-0.985, +1.162] |
| panel_neyman | carb | 3.933 | -0.058 [-0.617, +0.418] |
| panel_neyman | average | 6.374 | -0.029 [-0.521, +0.588] |
| reference_neyman | ever | 8.118 | -0.252 [-2.136, +1.811] |
| reference_neyman | weekly | 6.338 | -0.511 [-2.414, +1.191] |
| reference_neyman | carb | 3.617 | -0.373 [-1.462, +0.512] |
| reference_neyman | average | 6.024 | -0.379 [-1.453, +0.745] |
| panel_neyman_by_item | ever | 8.653 | +0.283 [-2.291, +2.708] |
| panel_neyman_by_item | weekly | 6.5 | -0.349 [-2.420, +1.403] |
| panel_neyman_by_item | carb | 3.718 | -0.273 [-1.337, +0.572] |
| panel_neyman_by_item | average | 6.29 | -0.113 [-1.195, +0.941] |
| reference_neyman_by_item | ever | 8.628 | +0.258 [-1.845, +2.389] |
| reference_neyman_by_item | weekly | 7.122 | +0.273 [-2.112, +2.899] |
| reference_neyman_by_item | carb | 3.582 | -0.408 [-1.767, +0.823] |
| reference_neyman_by_item | average | 6.444 | +0.041 [-1.084, +1.295] |

Panel Neyman minus reference Neyman: ever +0.255 [-1.495, +1.764], weekly +0.479 [-1.167, +2.042], carb +0.316 [-0.452, +1.246], average +0.350 [-0.557, +1.302]

## direct, pool_own, national_error (pp)

| allocation | item | mean | minus proportional |
|---|---|---|---|
| equal | ever | 2.652 | +0.092 [-2.184, +2.812] |
| equal | weekly | 2.34 | +0.106 [-2.391, +2.524] |
| equal | carb | 1.412 | -0.109 [-1.608, +1.116] |
| equal | average | 2.134 | +0.030 [-1.262, +1.224] |
| proportional | ever | 2.56 | - |
| proportional | weekly | 2.234 | - |
| proportional | carb | 1.52 | - |
| proportional | average | 2.105 | - |
| panel_neyman | ever | 2.606 | +0.046 [-0.948, +1.140] |
| panel_neyman | weekly | 2.226 | -0.008 [-1.357, +1.147] |
| panel_neyman | carb | 1.481 | -0.039 [-0.571, +0.402] |
| panel_neyman | average | 2.104 | -0.000 [-0.594, +0.651] |
| reference_neyman | ever | 2.445 | -0.115 [-2.437, +2.316] |
| reference_neyman | weekly | 2.145 | -0.089 [-2.164, +1.805] |
| reference_neyman | carb | 1.363 | -0.157 [-1.268, +0.749] |
| reference_neyman | average | 1.985 | -0.120 [-1.401, +1.023] |
| panel_neyman_by_item | ever | 2.507 | -0.053 [-2.386, +2.671] |
| panel_neyman_by_item | weekly | 2.145 | -0.089 [-1.952, +1.662] |
| panel_neyman_by_item | carb | 1.424 | -0.097 [-1.521, +0.860] |
| panel_neyman_by_item | average | 2.025 | -0.080 [-1.291, +1.072] |
| reference_neyman_by_item | ever | 2.578 | +0.018 [-2.049, +2.142] |
| reference_neyman_by_item | weekly | 2.19 | -0.044 [-3.040, +3.022] |
| reference_neyman_by_item | carb | 1.353 | -0.167 [-2.140, +0.997] |
| reference_neyman_by_item | average | 2.041 | -0.064 [-1.400, +1.222] |

Panel Neyman minus reference Neyman: ever +0.160 [-2.027, +2.271], weekly +0.081 [-1.618, +1.878], carb +0.118 [-0.677, +1.341], average +0.120 [-0.980, +1.366]

