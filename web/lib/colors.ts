// Series colours, in one plain module because a server component cannot read values exported from a client module.
// Checked with the dataviz palette script on #FFFFFF and #E9F4F5. The brief's teal #0A7488 fails its chroma floor (0.089), so
// marks use #00829B and teal text keeps #0A7488. Yuzu #F0A81E has 2.03:1 on white, so thin lines and dots use #B87C00 and large
// fills such as the liquid keep #F0A81E. All checks pass for 00829B, B87C00, 6C3FA5: CVD worst 17.2, normal worst 23.3, contrast >= 3:1.
// Meaning: real is real responses only, panel and yuzu are panel output only, grape is wrong direction and pierced attacks only.
// Everything else uses calibrated (ink) or reference (grey).
export const COLOR = {
  real: "#00829B",
  panel: "#B87C00",
  yuzu: "#F0A81E",
  yuzuSoft: "#FBDD9E",
  grape: "#6C3FA5",
  calibrated: "#12323B",
  reference: "#5B7881",
};
