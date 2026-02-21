export function normalizeAssociationBrand(rawBrand: string) {
  return rawBrand.toLowerCase().replace(/[^a-z0-9-]/g, "");
}
