import type { AssociationTheme } from "@/lib/api/types";

const LEGACY_THEME_TOKENS_BY_BRAND: Record<string, Record<string, string>> = {
  date: {
    "--primaryColor": "#000000",
    "--primaryColorLight": "#202020",
    "--primaryColorLighte": "#3d3d3d",
    "--primaryColorLighter": "#505050",
    "--primaryColorTransparent": "rgba(0, 0, 0, 0.9)",
    "--primaryColorTransparenter": "rgba(0, 0, 0, 0.8)",
    "--secondaryColor": "#ffffff",
    "--secondaryColorDarker": "#eaeaea",
    "--textColorLight": "#ffffff",
    "--textColorLightish": "#eaeaea",
    "--textColorDark": "#000000",
    "--textColorDarkish": "#202020",
    "--textColorMedium": "#606060",
    "--helpText": "#888888",
    "--helpTextLighter": "rgb(199, 199, 199)",
    "--linkColorDark": "#3a80c3",
    "--linkColorDarkHover": "#26547f",
    "--linkColorLight": "rgb(208, 255, 0)",
    "--linkColorLightHover": "rgb(146, 179, 0)",
  },
  kk: {
    "--primaryColor": "rgb(10, 140, 65)",
    "--primaryColorLight": "#2a693d",
    "--primaryColorLighte": "#3b8b53",
    "--primaryColorLighter": "rgb(10, 170, 77)",
    "--primaryColorTransparent": "rgba(10, 140, 65, 0.9)",
    "--primaryColorTransparenter": "rgba(10, 140, 65, 0.8)",
    "--secondaryColor": "#ffffff",
    "--secondaryColorDarker": "#e0e0e0",
    "--textColorLight": "#ffffff",
    "--textColorLightish": "#eaeaea",
    "--textColorDark": "#000000",
    "--textColorDarkish": "#202020",
    "--textColorMedium": "#606060",
    "--helpText": "#888888",
    "--helpTextLighter": "rgb(199, 199, 199)",
    "--linkColorDark": "#3a80c3",
    "--linkColorDarkHover": "#26547f",
    "--linkColor": "rgb(44, 148, 96)",
    "--linkColorSecondary": "rgb(10, 170, 77)",
    "--linkSecondaryHover": "#2a693d",
    "--linkColorLight": "rgb(37, 240, 122)",
    "--linkColorLightHover": "rgb(29, 185, 94)",
  },
  biocum: {
    "--primaryColor": "#225E41",
    "--primaryColorLight": "#2F4C42",
    "--primaryColorLighte": "#35564a",
    "--primaryColorLighter": "#3c6153",
    "--primaryColorTransparent": "rgba(34, 94, 65, 0.68)",
    "--primaryColorTransparenter": "rgba(0, 0, 0, 0.8)",
    "--secondaryColor": "#ffffff",
    "--secondaryColorDarker": "#f8f8f8",
    "--textColorLight": "#ffffff",
    "--textColorLightish": "#eaeaea",
    "--textColorDark": "#000000",
    "--textColorDarkish": "#202020",
    "--helpText": "rgb(171, 171, 171)",
    "--helpTextLighter": "rgb(199, 199, 199)",
    "--linkColor": "#49796b",
    "--linkColorHover": "#225E41",
    "--linkColorSecondary": "#49796b",
    "--linkSecondaryHover": "#225E41",
    "--linkColorLight": "#b9efd3",
    "--linkColorLightHover": "#9dd6ba",
  },
  on: {
    "--primaryColor": "#84030B",
    "--primaryColorLight": "#a8131d",
    "--primaryColorLighte": "#b52831",
    "--primaryColorLighter": "#df5b63",
    "--primaryColorTransparent": "rgba(132, 3, 11, 0.7)",
    "--primaryColorTransparenter": "rgba(132, 3, 11, 0.65)",
    "--secondaryColor": "#ffc400",
    "--secondaryColorDarker": "#131313",
    "--textColorLight": "#faf0dc",
    "--textColorLightish": "#faf0dc",
    "--textColorDark": "#000000",
    "--textColorDarkish": "#202020",
    "--textColorMedium": "#606060",
    "--helpText": "#faf0dc",
    "--helpTextLighter": "rgb(199, 199, 199)",
    "--linkColorDark": "#3a80c3",
    "--linkColorDarkHover": "#26547f",
    "--linkColorLight": "#ffc400",
    "--linkColorLightHover": "#edc057",
  },
  demo: {
    "--primaryColor": "#0000FF",
    "--primaryColorLight": "#2020FF",
    "--primaryColorLighte": "#3d3dFF",
    "--primaryColorLighter": "#5050FF",
    "--primaryColorTransparent": "rgba(0, 0, 255, 0.9)",
    "--primaryColorTransparenter": "rgba(0, 0, 255, 0.8)",
    "--secondaryColor": "#ffffff",
    "--secondaryColorDarker": "#eaeaea",
    "--textColorLight": "#ffffff",
    "--textColorLightish": "#eaeaea",
    "--textColorDark": "#000000",
    "--textColorDarkish": "#202020",
    "--textColorMedium": "#606060",
    "--helpText": "#888888",
    "--helpTextLighter": "rgb(199, 199, 199)",
    "--linkColorDark": "#0080FF",
    "--linkColorDarkHover": "#004080",
    "--linkColorLight": "rgb(0, 255, 255)",
    "--linkColorLightHover": "rgb(0, 192, 192)",
  },
};

export function normalizeAssociationBrand(rawBrand: string) {
  return rawBrand.toLowerCase().replace(/[^a-z0-9-]/g, "");
}

export function resolveUiProfile(brand: string) {
  switch (brand) {
    case "kk":
      return "kk";
    case "biocum":
      return "biocum";
    case "on":
      return "on";
    case "date":
    case "demo":
      return "legacy-default";
    default:
      return "default";
  }
}

export function buildThemeStyleVars(theme: AssociationTheme, brand: string) {
  const palette = theme.palette;
  const legacyBrandTokens = LEGACY_THEME_TOKENS_BY_BRAND[brand] ?? {};

  return {
    "--theme-background": palette.background,
    "--theme-surface": palette.surface,
    "--theme-text": palette.text,
    "--theme-text-muted": palette.text_muted,
    "--theme-primary": palette.primary,
    "--theme-secondary": palette.secondary,
    "--theme-accent": palette.accent,
    "--theme-border": palette.border,
    "--theme-font-heading": theme.font_heading,
    "--theme-font-body": theme.font_body,
    "--primaryColor": palette.primary,
    "--primaryColorLight": `color-mix(in srgb, ${palette.primary} 82%, #000000)`,
    "--primaryColorLighte": `color-mix(in srgb, ${palette.primary} 66%, #000000)`,
    "--primaryColorLighter": `color-mix(in srgb, ${palette.primary} 52%, #000000)`,
    "--primaryColorTransparent": `color-mix(in srgb, ${palette.primary} 90%, transparent)`,
    "--primaryColorTransparenter": `color-mix(in srgb, ${palette.primary} 80%, transparent)`,
    "--secondaryColor": palette.secondary,
    "--secondaryColorDarker": `color-mix(in srgb, ${palette.secondary} 85%, #d9d9d9)`,
    "--textColorLight": palette.background,
    "--textColorLightish": `color-mix(in srgb, ${palette.background} 88%, ${palette.text} 12%)`,
    "--textColorDark": palette.text,
    "--textColorDarkish": `color-mix(in srgb, ${palette.text} 88%, black 12%)`,
    "--textColorMedium": palette.text_muted,
    "--helpText": `color-mix(in srgb, ${palette.background} 76%, ${palette.text} 24%)`,
    "--helpTextLighter": `color-mix(in srgb, ${palette.background} 66%, ${palette.text} 34%)`,
    "--linkColorDark": palette.accent,
    "--linkColorDarkHover": `color-mix(in srgb, ${palette.accent} 78%, black 22%)`,
    "--linkColorLight": palette.secondary,
    "--linkColorLightHover": `color-mix(in srgb, ${palette.secondary} 78%, white 22%)`,
    "--warning": "#d89992",
    "--warning-darker": "#d55b4e",
    "--navClickHighlight": "rgba(255, 255, 255, 0.25)",
    "--navHoverHighlight": "rgba(255, 255, 255, 0.15)",
    "--defaultPadding": "20px",
    "--defaultRadius": "5px",
    ...legacyBrandTokens,
  } satisfies Record<string, string>;
}
