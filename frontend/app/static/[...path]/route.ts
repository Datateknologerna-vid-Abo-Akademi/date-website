import { proxyAssetPath } from "@/lib/http/asset-proxy";

interface AssetRouteContext {
  params: Promise<{ path: string[] }>;
}

export async function GET(_: Request, context: AssetRouteContext) {
  const { path } = await context.params;
  return proxyAssetPath("/static", path);
}
